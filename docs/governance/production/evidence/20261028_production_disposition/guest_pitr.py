"""Actual isolated PostgreSQL18 base/WAL recovery and protected second filesystem."""

import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import tarfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath

B = Path('/srv/bonira')
OUT = B / 'production-disposition-evidence'
WORK = B / 'pitr-production'
VAULT = Path('/srv/bonira-production-vault')
KEYS = Path('/srv/bonira-production-key-custody')
STAGE = Path('/srv/bonira-production-capture')
SOURCE = B / 'source-production-disposition'
os.umask(0o077)
OUT.mkdir(exist_ok=True);os.chown(OUT,10001,10001)
sys.path.insert(0,str(SOURCE))
from scripts.production_recovery import encrypt, decrypt, file_hash, separate_boundaries, RecoveryError


def save(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2,default=str)+'\n')


def run(args, *, input=None, allow=False):
    result = subprocess.run([str(a) for a in args],input=input,capture_output=True,text=True,check=False)
    if result.returncode and not allow:
        logs=B/'private-logs';logs.mkdir(exist_ok=True)
        (logs/('pitr-'+secrets.token_hex(5)+'.txt')).write_text(result.stdout+result.stderr)
        raise RuntimeError('Owned PITR command failed: '+str(args[0])+'; private diagnostics retained')
    return result


def sql(statement,container='bonira-pitr-source',database='pe_gate11_20261028'):
    return run(['docker','exec','-i',container,'psql','-X','-v','ON_ERROR_STOP=1','-U','bonira_admin','-d',database,'-At'],input=statement).stdout.strip()


def ready(name,seconds=90):
    for _ in range(seconds):
        if run(['docker','exec',name,'pg_isready','-U','bonira_admin'],allow=True).returncode==0:return
        time.sleep(1)
    raise RuntimeError('Owned PostgreSQL did not become ready')


def fingerprint(name,label):
    # Complete database row/constraint/sequence fingerprint via native psql; no raw rows exported.
    tables=sql("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename",name).splitlines()
    rows={}
    for table in tables:
        assert table.replace('_','').isalnum()
        raw=sql('SELECT row_to_json(t)::text FROM "'+table+'" t ORDER BY row_to_json(t)::text',name)
        lines=raw.splitlines() if raw else []
        rows[table]={'rows':len(lines),'sha256':hashlib.sha256('\n'.join(lines).encode()).hexdigest()}
    constraints=sql("SELECT conname,pg_get_constraintdef(oid) FROM pg_constraint WHERE connamespace='public'::regnamespace ORDER BY conname,pg_get_constraintdef(oid)",name)
    sequences=sql("SELECT schemaname,sequencename,start_value,min_value,max_value,increment_by,cycle,cache_size,last_value FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename",name)
    result={'tables':rows,'constraints_sha256':hashlib.sha256(constraints.encode()).hexdigest(),'sequences_sha256':hashlib.sha256(sequences.encode()).hexdigest()}
    save(label+'_FINGERPRINT.json',result)
    return result


def extract_regular(archive,directory):
    # Guest system Python predates tarfile extraction filters. Accept only
    # regular files/directories in our verified captures, never links or devices.
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            name=PurePosixPath(member.name)
            assert not name.is_absolute() and '..' not in name.parts
            target=directory.joinpath(*name.parts)
            assert target.resolve().is_relative_to(directory.resolve())
            if member.isdir():target.mkdir(parents=True,exist_ok=True);target.chmod(member.mode & 0o777)
            else:
                assert member.isfile()
                target.parent.mkdir(parents=True,exist_ok=True)
                with tar.extractfile(member) as source,target.open('xb') as output:shutil.copyfileobj(source,output)
                target.chmod(member.mode & 0o777)


def start_restore(name,directory,archive,target):
    uid=int((WORK/'uid').read_text())
    original_directory=directory;attempt=1
    while directory.exists():
        attempt+=1;directory=original_directory.with_name(original_directory.name+'-attempt'+str(attempt))
    directory.mkdir(mode=0o700)
    extract_regular(STAGE/'base.tar.gz',directory)
    # Base contains server-generated config only; credentials/TLS private keys are external.
    (directory/'recovery.signal').touch()
    with (directory/'postgresql.auto.conf').open('a') as f:
        f.write("\nrestore_command = 'cp /archive/%f %p'\nrecovery_target_name = '"+target+"'\nrecovery_target_action = 'promote'\n")
    run(['chown','-R',str(uid)+':'+str(uid),directory])
    return run(['docker','run','-d','--name',name,'--network','bonira-pe','-v',str(directory)+':/var/lib/postgresql/18/docker','-v',str(archive)+':/archive:ro',IMAGE,'postgres','-c','archive_mode=off'])


def main():
    global IMAGE
    IMAGE=run(['docker','inspect','bonira-db','--format','{{.Image}}']).stdout.strip()
    assert IMAGE.startswith('sha256:')
    if not WORK.exists():
        WORK.mkdir(mode=0o700);KEYS.mkdir(mode=0o700);STAGE.mkdir(mode=0o700)
        # Separate mounted filesystem, not a directory under application/database storage.
        image=Path('/var/lib/bonira-production-vault.img')
        assert not image.exists() and not VAULT.exists()
        run(['truncate','-s','1536M',image]);image.chmod(0o600)
        run(['mkfs.ext4','-q',image]);VAULT.mkdir(mode=0o700)
        run(['mount','-o','loop,nodev,nosuid,noexec',image,VAULT]);VAULT.chmod(0o700)
        separate_boundaries(WORK,VAULT,KEYS)
        assert VAULT.stat().st_dev != WORK.stat().st_dev
        run(['openssl','req','-x509','-newkey','rsa:3072','-nodes','-keyout',KEYS/'backup.key','-out',KEYS/'recipient.crt','-days','7','-subj','/CN=BONIRA-synthetic-recovery-recipient'])
        (KEYS/'backup.key').chmod(0o600)
        shutil.copyfile(KEYS/'recipient.crt',STAGE/'recipient.crt')
        # Writer/public certificate and recovery private-key custodian are distinct POSIX principals.
        os.chown(KEYS,20003,20003);os.chown(KEYS/'backup.key',20003,20003)
        os.chown(VAULT,20002,20002)
        probe=run(['setpriv','--reuid','20002','--regid','20002','--clear-groups','test','-r',KEYS/'backup.key'],allow=True)
        assert probe.returncode!=0
        uid=int(run(['docker','run','--rm','--entrypoint','id',IMAGE,'-u','postgres']).stdout)
        (WORK/'uid').write_text(str(uid))
        for folder in ['data','wal-spool','backup','restore-archive','missing-archive','facts','scripts']:
            (WORK/folder).mkdir(mode=0o700)
        for folder in ['data','wal-spool','backup','restore-archive','missing-archive']:
            os.chown(WORK/folder,uid,uid)
        password=secrets.token_urlsafe(36);app_password=secrets.token_urlsafe(36);repl_password=secrets.token_urlsafe(36)
        (WORK/'admin-password').write_text(password);(WORK/'app-password').write_text(app_password)
        (WORK/'repl.pgpass').write_text('db:5432:replication:bonira_backup:'+repl_password+'\n')
        os.chown(WORK/'repl.pgpass',uid,uid)
        env=WORK/'postgres.env';env.write_text('POSTGRES_USER=bonira_admin\nPOSTGRES_PASSWORD_FILE=/run/secrets/admin-password\nPOSTGRES_DB=pe_gate11_20261028\nPOSTGRES_INITDB_ARGS=--auth-host=scram-sha-256\n')
        archive=WORK/'scripts/wal_archive.sh'
        archive.write_text('#!/bin/sh\nset -eu\nif test -f "/wal-spool/$2"; then cmp "$1" "/wal-spool/$2"; else cp "$1" "/wal-spool/$2"; fi\n')
        archive.chmod(0o755);(WORK/'scripts').chmod(0o755)  # Script-only directory, no secrets.
        run(['docker','network','create','--internal','bonira-pitr-network'])
        run(['docker','run','-d','--name','bonira-pitr-source','--network','bonira-pitr-network','--network-alias','db','--env-file',env,'-v',str(WORK/'data')+':/var/lib/postgresql','-v',str(WORK/'admin-password')+':/run/secrets/admin-password:ro','-v',str(WORK/'wal-spool')+':/wal-spool','-v',str(WORK/'scripts')+':/scripts:ro','-v',str(B/'pki/ca.crt')+':/tls/ca.crt:ro','-v',str(B/'pki/db.crt')+':/tls/db.crt:ro','-v',str(B/'pki/db.key')+':/tls/db.key:ro',IMAGE,'postgres','-c','ssl=on','-c','ssl_cert_file=/tls/db.crt','-c','ssl_key_file=/tls/db.key','-c','ssl_ca_file=/tls/ca.crt','-c','archive_mode=on','-c','archive_command=/scripts/wal_archive.sh %p %f','-c','archive_timeout=60s','-c','wal_level=replica'])
        ready('bonira-pitr-source')
    if not (OUT/'PITR_CAPTURE.json').exists():
        if not (OUT/'PITR_CUTOFF.json').exists():
            uid=int((WORK/'uid').read_text())
            app_password=(WORK/'app-password').read_text()
            repl_password=(WORK/'repl.pgpass').read_text().strip().split(':')[-1]
            ready('bonira-pitr-source')
            for _ in range(60):
                if run(['docker','exec','bonira-pitr-source','psql','-X','-U','bonira_admin','-d','pe_gate11_20261028','-Atc','SELECT 1'],allow=True).returncode==0:break
                time.sleep(1)
            if sql("SELECT count(*) FROM pg_roles WHERE rolname='bonira_app'")=='0':
                sql("CREATE ROLE bonira_app LOGIN PASSWORD '"+app_password+"'; CREATE ROLE bonira_backup LOGIN REPLICATION PASSWORD '"+repl_password+"';")
            run(['docker','start','bonira-db']);ready('bonira-db')
            # Reuse qualified full schema and synthetic records; no migration or retired-data revisit.
            if sql("SELECT to_regclass('gate11_recovery_probe') IS NOT NULL")=='f':
                dump=run(['docker','exec','-e','PGSERVICEFILE=/tmp/bonira-service.conf','bonira-db','pg_dump','--dbname=service=bonira_shared dbname=pe_legacy_20261028_populated_retry1','--no-owner','--no-privileges']).stdout
                run(['docker','exec','-i','bonira-pitr-source','psql','-X','-v','ON_ERROR_STOP=1','-U','bonira_admin','-d','pe_gate11_20261028'],input=dump)
                sql('CREATE TABLE gate11_recovery_probe (id integer PRIMARY KEY, label text NOT NULL); INSERT INTO gate11_recovery_probe VALUES (1,\'before_base\');')
            subnet=json.loads(run(['docker','network','inspect','bonira-pitr-network']).stdout)[0]['IPAM']['Config'][0]['Subnet']
            import ipaddress
            ipaddress.ip_network(subnet)
            hba=WORK/'data/18/docker/pg_hba.conf'
            if 'hostssl replication bonira_backup' not in hba.read_text():
                with hba.open('a') as f:f.write('\nhostssl replication bonira_backup '+subnet+' scram-sha-256\n')
            sql('SELECT pg_reload_conf()')
            # Native base capture uses a distinct replication-only credential and verified TLS.
            run(['docker','run','--rm','--network','bonira-pitr-network','--user',str(uid),'-e','PGPASSFILE=/run/secrets/repl.pgpass','-v',str(WORK/'repl.pgpass')+':/run/secrets/repl.pgpass:ro','-v',str(B/'pki/ca.crt')+':/tls/ca.crt:ro','-v',str(WORK/'backup')+':/backup',IMAGE,'pg_basebackup','-d','host=db user=bonira_backup sslmode=verify-full sslrootcert=/tls/ca.crt','-D','/backup/base','-Fp','-X','stream','--checkpoint=fast'])
            run(['docker','run','--rm','--user',str(uid),'-v',str(WORK/'backup')+':/backup:ro',IMAGE,'pg_verifybackup','/backup/base'])
            with tarfile.open(STAGE/'base.tar.gz','w:gz') as tar:
                tar.add(WORK/'backup/base',arcname='.')
            for klass in ['document_media','configuration_metadata','audit_operational']:
                target=WORK/'facts'/klass
                shutil.copytree(B/'shared'/klass,target)
                (target/'GATE11-production-qualification.txt').write_text('Synthetic governed '+klass+' snapshot\n')
            sql("INSERT INTO gate11_recovery_probe VALUES (2,'after_base'); SELECT pg_create_restore_point('bonira_gate11_target');")
            save('PITR_CUTOFF.json',{'at':datetime.now(UTC).isoformat(),'target':'bonira_gate11_target','state':'after_base committed; after_target absent','production':False})
            # Full fingerprint at the selected recovery point, before the later committed marker.
            expected=fingerprint('bonira-pitr-source','PITR_EXPECTED')
            sql("INSERT INTO gate11_recovery_probe VALUES (3,'after_target'); SELECT pg_switch_wal();")
            for _ in range(90):
                archived=int(sql('SELECT archived_count FROM pg_stat_archiver'))
                if archived>=2:break
                time.sleep(1)
            else:raise RuntimeError('No continuous archived WAL')
        else:
            expected=json.loads((OUT/'PITR_EXPECTED_FINGERPRINT.json').read_text())
        captures={}
        captures['base']=encrypt(STAGE/'base.tar.gz',VAULT/'base.cms',certificate=STAGE/'recipient.crt')
        with tarfile.open(STAGE/'files.tar.gz','w:gz') as tar:
            for klass in ['document_media','configuration_metadata','audit_operational']:
                tar.add(WORK/'facts'/klass,arcname=klass)
        captures['files']=encrypt(STAGE/'files.tar.gz',VAULT/'files.cms',certificate=STAGE/'recipient.crt')
        for wal in sorted((WORK/'wal-spool').iterdir()):
            captures[wal.name]=encrypt(wal,VAULT/(wal.name+'.cms'),certificate=STAGE/'recipient.crt')
        assert not any(p.suffix=='.key' for p in VAULT.iterdir())
        save('PITR_CAPTURE.json',{'result':'PASS','captures':captures,'archive_mode':sql('SHOW archive_mode'),'archive_timeout':sql('SHOW archive_timeout'),'wal_level':sql('SHOW wal_level'),'base_verified':True,'second_filesystem':True,'backup_writer_cannot_read_private_key':True,'separate_db_app_replication_credentials':True,'retain_until':(datetime.now(UTC)+timedelta(days=30)).isoformat(),'purge_authorized':False,'production':False})
    else:
        assert (OUT/'PITR_CAPTURE.json').exists(),'Previous partial attempt retained; resume explicitly'
        expected=json.loads((OUT/'PITR_EXPECTED_FINGERPRINT.json').read_text())
    # Recover entirely from encrypted second-boundary artifacts, not live storage.
    started=time.monotonic()
    restored=STAGE/'decrypted';restored.mkdir(mode=0o700,exist_ok=True)
    for artifact in sorted(VAULT.glob('*.cms')):
        output=restored/artifact.stem
        if not output.exists():decrypt(artifact,output,certificate=STAGE/'recipient.crt',private_key=KEYS/'backup.key')
        name='base' if artifact.stem=='base' else 'files' if artifact.stem=='files' else artifact.stem
        capture=json.loads((OUT/'PITR_CAPTURE.json').read_text())['captures'][name]
        assert file_hash(output)==capture['plaintext_sha256']
    # No live source, TLS private-key or credential dependency is needed for replay.
    run(['docker','stop','--time','30','bonira-pitr-source'])
    uid=int((WORK/'uid').read_text())
    for artifact in restored.iterdir():
        if artifact.name not in ['base','files']:
            target=WORK/'restore-archive'/artifact.name;shutil.copyfile(artifact,target);os.chown(target,uid,uid)
    # The plaintext base is already present only in the separate recovery workspace;
    # verify decryption equality then use that exact recovered copy.
    assert file_hash(restored/'base')==file_hash(STAGE/'base.tar.gz')
    shutil.copyfile(restored/'base',STAGE/'restore-base.tar.gz')
    # start_restore consumes the decrypted bytes (not the original source archive).
    original=STAGE/'base.tar.gz';
    if not (STAGE/'original-base.tar.gz').exists():original.rename(STAGE/'original-base.tar.gz');shutil.copyfile(restored/'base',original)
    start_restore('bonira-pitr-missing',WORK/'missing-data',WORK/'missing-archive','bonira_gate11_target')
    time.sleep(8)
    logs=run(['docker','logs','bonira-pitr-missing'],allow=True)
    no_target='recovery ended before configured recovery target was reached' in logs.stderr+logs.stdout
    assert no_target,'Missing WAL must not report successful target recovery'
    run(['docker','stop','bonira-pitr-missing'],allow=True)
    start_restore('bonira-pitr-restored',WORK/'restored-data',WORK/'restore-archive','bonira_gate11_target')
    ready('bonira-pitr-restored')
    for _ in range(90):
        if sql('SELECT pg_is_in_recovery()','bonira-pitr-restored')=='f':break
        time.sleep(1)
    assert sql('SELECT id FROM gate11_recovery_probe ORDER BY id','bonira-pitr-restored')=='1\n2'
    actual=fingerprint('bonira-pitr-restored','PITR_ACTUAL')
    assert actual==expected,'Full database differs at target'
    files_restore=STAGE/'restored-facts';files_restore.mkdir(mode=0o700)
    extract_regular(restored/'files',files_restore)
    files=0
    for file in (WORK/'facts').rglob('*'):
        if file.is_file():
            assert file_hash(file)==file_hash(files_restore/file.relative_to(WORK/'facts'));files+=1
    # Authenticated encryption rejects corruption and a wrong private key, publishing no plaintext.
    bad=VAULT/'corrupt.cms';data=bytearray((VAULT/'files.cms').read_bytes());data[-20]^=1;bad.write_bytes(data)
    failures=[]
    for label,artifact,key in [('corruption',bad,KEYS/'backup.key'),('wrong_key',VAULT/'files.cms',B/'pki/db.key')]:
        try:decrypt(artifact,restored/label,certificate=STAGE/'recipient.crt',private_key=key)
        except RecoveryError:failures.append(label)
        else:raise AssertionError('Unauthenticated recovery succeeded')
        assert not (restored/label).exists()
    elapsed=time.monotonic()-started
    assert elapsed<=3600
    save('PITR_RESULT.json',{'result':'PASS','postgres_image':IMAGE,'target':'bonira_gate11_target','before_base_and_after_base_restored':True,'later_committed_row_excluded':True,'source_stopped_during_restore':True,'complete_database_fingerprint_equal':True,'tables':len(expected['tables']),'rows':sum(v['rows'] for v in expected['tables'].values()),'file_classes':3,'files_equal':files,'native_pg_verifybackup':'PASS','missing_wal_fails_closed':no_target,'negative_encryption_controls':failures,'recovery_seconds':elapsed,'rto_limit_seconds':3600,'all_four_classes':True,'no_secret_or_key_contents_exported':True,'production':False})
    print('PASS: actual base+WAL point-in-time recovery, complete state/files, protected encrypted custody',flush=True)


if __name__=='__main__':main()
