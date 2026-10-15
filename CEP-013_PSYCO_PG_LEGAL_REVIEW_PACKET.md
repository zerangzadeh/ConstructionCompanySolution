> Historical review packet. Current decision: pure `psycopg 3.3.5` has a bounded `APPROVE_WITH_CONDITION` disposition; `psycopg-binary 3.3.5` is rejected and absent from the approved CEP-013 Linux sets. See `CEP-013_LICENSE_DISPOSITION_PACKET.md`.

# CEP-013 Psycopg exact-artifact external legal review packet

**Status:** Both artifacts remain unapproved (`EXTERNAL_LEGAL_REVIEW_REQUIRED`). The license gate is BLOCKED. This packet requests external legal disposition; it makes no compatibility determination. Identity and license hashes below come from `CEP-013_LICENSE_DISPOSITION_PACKET.md`, `output/cep-013/gate/licenses-dev.json`, and the exact wheels in `output/cep-013/artifacts/dev/`.

## Known BONIRA use and distribution facts

- BONIRA is a multi-tenant construction SaaS. Its Django settings use `django.db.backends.postgresql`; the approved direct runtime requirement is `psycopg[binary]`. These two exact wheels are in the eight-package Linux runtime set for CPython 3.11.17, Debian 12, `linux/amd64`.
- The approved build acquires hash-checked wheels from HTTPS PyPI and retains an attested wheelhouse. Planned production deployment installs offline from that wheelhouse. A pinned official Python image is the build target, **not** an approved production container topology or distribution plan.
- Whether BONIRA will provide either wheel, the wheelhouse, or an image containing them to customers or third parties is **not established**. No BONIRA modifications to these exact wheel artifacts are evidenced; an intended modification or component rebuild is **not established**. No production deployment is approved.

## psycopg 3.3.5

| Field | Exact evidence |
| --- | --- |
| Artifact | `psycopg-3.3.5-py3-none-any.whl` |
| Wheel SHA-256 | `ce5aa5cdb4f9379f00f487590e5890bfa7df9a164648c969ffa628505e21af4e` |
| Captured license | Wheel `METADATA`: `License-Expression: LGPL-3.0-only`; `License-File: LICENSE.txt`. Inventory combined license-text SHA-256: `6a69afa6c787c3fb59951585ee1d7b821ec62efda1efc17d3946a9648e801f50`. Embedded `LICENSE.txt` file SHA-256: `e3a994d82e644b03a792a930f574002658412f62407f5fee083f2555c5f23118`. |
| Relevant embedded text | LGPL v3 (29 June 2007) says it incorporates GNU GPL v3. Section 0 defines Library, Application, Combined Work, Minimal Corresponding Source and Corresponding Application Code. Section 2 addresses conveying certain modified versions; section 3 addresses object code with nontrivial Library header material; section 4 states conditions for conveying a Combined Work, including notice, GNU GPL/LGPL copies, conditional displayed copyright notice, and a source/relinking or suitable shared-library path; section 5 addresses combined libraries. A separate GNU GPL v3 copy or source-offer statement was not identified among the wheel's license-like files. |
| Native components | No native `.so` files were found in this wheel; it contains Python source files. This finding does not cover separate installed packages or system libraries. |

**Questions for external counsel:** For the known SaaS runtime use and any proposed customer/third-party wheelhouse or image distribution, which conveying/Combined Work terms apply? What exact notice and license-copy materials are required, including the incorporated GPL text? If distribution occurs, which section 4 source/relinking or shared-library path applies and what corresponding materials must BONIRA provide? Would modification of this library change those obligations? Please identify what deployment/distribution facts are still needed to decide.

## psycopg-binary 3.3.5

| Field | Exact evidence |
| --- | --- |
| Artifact | `psycopg_binary-3.3.5-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.whl` |
| Wheel SHA-256 | `d8b66353b20e79bf7ac0a80f03ae97f522ccbbf909d687eec62f112e56c0276d` |
| Captured license | Wheel `METADATA`: `License-Expression: LGPL-3.0-only`; `License-File: LICENSE.txt`. Inventory combined license-text SHA-256: `15fe0ee0375df2269400514492c824d7b8a4c098882904855bc361235ca92c0c`. Embedded `LICENSE.txt` file SHA-256: `e3a994d82e644b03a792a930f574002658412f62407f5fee083f2555c5f23118` (byte-identical to the psycopg file). |
| Relevant embedded text | The same LGPL v3 sections 0, 2, 3, 4 and 5 described above, including the conditional conveying, modification, notice, license-copy, and source/relinking or shared-library terms. The wheel contains no separate GNU GPL v3 text or component-specific license files. |
| Native components | Two native modules: `psycopg_binary/_psycopg.cpython-311-x86_64-linux-gnu.so` and `psycopg_binary/pq.cpython-311-x86_64-linux-gnu.so`. Fifteen bundled shared libraries under `psycopg_binary.libs/`: `libcom_err`, `libcrypt`, `libcrypto`, `libgssapi_krb5`, `libk5crypto`, `libkeyutils`, `libkrb5`, `libkrb5support`, `liblber`, `libldap`, `libpcre`, `libpq`, `libsasl2`, `libselinux`, and `libssl` (each wheel entry has a hashed filename). The wheel has no separately identified license, notice, source bundle, source offer, or build/provenance record for those components. The package-level LGPL expression does not establish their individual licenses. |

**Questions for external counsel:** For known SaaS use and any proposed wheelhouse/image transfer, what LGPL terms apply to this native distribution, and what notice, license-copy, source, relinking or installation materials would be required? What are the licenses and redistribution/source obligations of each bundled shared library, and what provenance or source evidence is needed to establish compliance? Does the packaging/linkage of the two modules and 15 libraries alter the applicable Combined Work analysis? What changes if BONIRA modifies or rebuilds any component? Please identify the missing distribution/topology facts needed for a bounded disposition.
