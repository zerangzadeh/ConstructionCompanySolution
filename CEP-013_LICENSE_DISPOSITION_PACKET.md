# CEP-013 exact artifact license disposition packet

**Current status (2026-10-16):** The approved Linux sets contain 15 exact artifacts: the 14 Product Owner approved artifacts plus pure `psycopg 3.3.5` (`APPROVE_WITH_CONDITION`). The rejected `psycopg-binary 3.3.5` wheel is absent from both Linux locks. Exact-artifact approvals are recorded in `security/supply_chain/license_approvals.json`; the regenerated local license gate is **PASS**. The historical review below remains evidence of the removed artifact and earlier decision state. The CEP-013 license gate is PASS; the scoped CEP-013 development closure is recorded in `CEP-013_COMPLETION_REPORT.md`. Signed release attestation remains a later production gate.

The table is derived from the acquired CPython 3.11.17 Debian 12 linux/amd64 development wheelhouse. The production set is its eight-package subset. The exact wheel license files and metadata are retained in `output/cep-013/gate/licenses-dev.json`; the hash below is over the complete wheel. Inspect the exact wheel license text before accepting any commercial/SaaS obligation.

| Package | Version | Wheel SHA-256 | Declared license | License-text SHA-256 |
| --- | --- | --- | --- | --- |
| asgiref | 3.12.1 | `fe386d1c2bff7259ea95929266d12a8cf9a8b5a1c2598402967d8792e7a7c094` | BSD-3-Clause | `82021d905cf19cac82deecabf9507489a4ed1185030514d7d25bcd40b394d85b` |
| colorama | 0.4.6 | `4f1d9991f5acc0ca119f9d443620b77f9d6b33703e51011c16baf57afb285fc6` | Undeclared in metadata; BSD-3-Clause terms in wheel text | `c5675679e48942a0a273c9d42fb20c838580854538426a60ca317d50bbf8a37d` |
| django | 5.2.17 | `f04fb3b36ee119e1af4fa1d397d5fd6cf12700f49321e84d4f4c642c5b1973db` | BSD-3-Clause | `57129e8377f2dad46713697110b8aa282bebf944495c269e6ac43a140a500b8e` |
| iniconfig | 2.3.1 | `9121e2c1fdb355232495be3194c8dfe87ccc2d5dee45947b78e68f499790d7a7` | MIT | `7e88956c8f52e374fc49f208db818442b5dbe151496efa271e5cd2c346df2a83` |
| packaging | 26.3 | `d7193f7c8e4e93f444fde0262bf90af30e16fa0ad0ad44cb553c87339b23cd1c` | Apache-2.0 OR BSD-2-Clause | `abac410b22eeb977a9d5c0770e553cdd6db631ff4be3f10c44597992952c628d` |
| pluggy | 1.6.0 | `e920276dd6813095e9377c0bc5566d94c932c33b27a3e3945d8389c374dd4746` | MIT | `5cc7a82801e6cf15950d5950475f38ba3e00b064f81064c6d2ec4690a8a4a5c1` |
| psycopg | 3.3.5 | `ce5aa5cdb4f9379f00f487590e5890bfa7df9a164648c969ffa628505e21af4e` | LGPL-3.0-only | `6a69afa6c787c3fb59951585ee1d7b821ec62efda1efc17d3946a9648e801f50` |
| psycopg-binary | 3.3.5 | `d8b66353b20e79bf7ac0a80f03ae97f522ccbbf909d687eec62f112e56c0276d` | LGPL-3.0-only | `15fe0ee0375df2269400514492c824d7b8a4c098882904855bc361235ca92c0c` |
| pygments | 2.21.0 | `2363c69b61c4a97c838da3b130dcd6468f4848992b21a82f2a63ec34377137d9` | BSD-2-Clause | `6f55ffabf3bc7d9d2267660cd7c517ffd88125d242fc3b31f4b1be1520fbc9c3` |
| pytest | 9.1.1 | `37a86b45efb9a47a61a36449063e8e18d0cab3161329fc099eb21783169c4f0c` | MIT | `a649f45baae284481ba1fc756890e427ec5fa14ce868d4457104c35a996c2265` |
| pytest-django | 4.14.0 | `c533b08d89cc675efcd5398eea270b34547e35f9a3608e2c9748dd88428ea187` | pytest-django is released under the BSD (3-clause) license
        ----------------------------------------------------------
        Copyright (c) 2015-2018, pytest-django authors (see AUTHORS file)
        All rights reserved.
        
        Redistribution and use in source and binary forms, with or without
        modification, are permitted provided that the following conditions are met:
        
         * Redistributions of source code must retain the above copyright notice, this
           list of conditions and the following disclaimer.
         * Redistributions in binary form must reproduce the above copyright notice,
           this list of conditions and the following disclaimer in the documentation
           and/or other materials provided with the distribution.
         * The names of its contributors may not be used to endorse or promote products
           derived from this software without specific prior written permission.
        
        THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
        ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
        WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
        DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
        ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
        (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
        LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
        ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
        (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
        SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
        
        
        This version of pytest-django is a fork of pytest_django created by Ben Firshman.
        ---------------------------------------------------------------------------------
        Copyright (c) 2009, Ben Firshman
        All rights reserved.
        
        Redistribution and use in source and binary forms, with or without
        modification, are permitted provided that the following conditions are met:
        
         * Redistributions of source code must retain the above copyright notice, this
           list of conditions and the following disclaimer.
         * Redistributions in binary form must reproduce the above copyright notice,
           this list of conditions and the following disclaimer in the documentation
           and/or other materials provided with the distribution.
         * The names of its contributors may not be used to endorse or promote products
           derived from this software without specific prior written permission.
        
        THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
        ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
        WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
        DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
        ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
        (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
        LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
        ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
        (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
        SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
         | `341e242c187f94e9a810340df9877c27d3bb92dce35095702e3e7e8c1af81254` |
| python-dotenv | 1.2.3 | `904552145e8bfed22162c09dab1c2b9b54fefa7b23ba780f4f26ca0316b0f0d9` | BSD-3-Clause | `6f2c1b72c3d2070a8482227a9d80aaca05ccf1a98d50ab1e5c9a7af911e4f6f8` |
| ruff | 0.16.5 | `ef0f69e191a13a3c9816f63163c88790cb12cd157bbbb384e9c44745702ab105` | MIT | `d923b846ed454336c9ebcb5fbccc030191f3cbddf0e6e2abed09e52933931334` |
| sqlparse | 0.6.0 | `b861c0288ce2fa56209a9a6412d2e066ac664b3873b89c26c9d8415e8e32996f` | Undeclared in metadata; BSD-3-Clause terms in wheel text | `76d4029e02bb1eecee8fd9633b4e9a8ac98306ff7f044d723f56589484a1e8dd` |
| typing-extensions | 4.16.0 | `481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8` | PSF-2.0 | `0144551586cb4785e40d4678f4bc4486fe7983af7b3f18f3b0fcdab8f4c17b7c` |
| tzdata | 2026.5 | `b683bd1b6659ddcd810ff02ad09ba821d4bf1065072805063eb35c49617905ac` | Apache-2.0 | `f3baaafd281dfc75fa1b901ca34d7ff154157886d194c9b66e3cdf83c63c8aea` |

**Required disposition:** The Product Owner, with legal review where required, records `ALLOW` only after exact-artifact review and a compatibility reason in `security/supply_chain/license_approvals.json`. Unknown/rejected or changed terms remain `BLOCK`. The Product Owner decision recorded below is not a machine-readable gate entry; the two Psycopg artifacts remain unapproved, and no compatibility conclusion is inferred. The security reviewer verifies inventory/provenance, and the independent certification owner checks completeness.

This review does not authorize any package/version change, production action, Human Sign-off, or bypass of the vulnerability and provenance gates.

## Bounded Product Owner disposition recommendation

The table preserves the original recommendation and exact wheel evidence. The Product Owner's subsequent bounded approval is recorded below; it does not change the gate. The wheel filename and license evidence below are from `output/cep-013/gate/licenses-dev.json`. A license-text digest proves the captured text's identity; it does not, by itself, establish the terms of an undeclared license. For `APPROVE_WITH_CONDITION`, retain the exact artifact's applicable copyright/license notices in any distributed wheelhouse, image, or other redistribution, and reassess if the artifact, usage, or distribution model changes.

| Package | Version | Artifact / wheel | Detected license | License evidence | Recommended disposition | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| asgiref | 3.12.1 | `asgiref-3.12.1-py3-none-any.whl` | BSD-3-Clause | Declared license; wheel `LICENSE` captured, text SHA-256 above | APPROVE_WITH_CONDITION | Permissive declared terms; retain copyright/license/disclaimer on redistribution. |
| colorama | 0.4.6 | `colorama-0.4.6-py2.py3-none-any.whl` | BSD-3-Clause terms in wheel text (no SPDX expression) | BSD classifier and embedded `LICENSE.txt`; exact text reviewed below | EVIDENCE_SUFFICIENT_FOR_PRODUCT_OWNER_DECISION | The three redistribution conditions are explicit in the wheel license; Product Owner disposition remains unrecorded. |
| django | 5.2.17 | `django-5.2.17-py3-none-any.whl` | BSD-3-Clause | SPDX expression; `AUTHORS`, `LICENSE`, and `LICENSE.python` captured, combined text SHA-256 above | APPROVE_WITH_CONDITION | Retain all applicable notices, including the separately recorded Python license file, on redistribution. |
| iniconfig | 2.3.1 | `iniconfig-2.3.1-py3-none-any.whl` | MIT | SPDX expression; wheel `LICENSE` captured, text SHA-256 above | APPROVE_WITH_CONDITION | Retain the copyright and permission notice on redistribution. |
| packaging | 26.3 | `packaging-26.3-py3-none-any.whl` | Apache-2.0 OR BSD-2-Clause | SPDX expression; wheel license file/hash recorded above | APPROVE_WITH_CONDITION | Record the selected license alternative and satisfy its applicable notices before redistribution. |
| pluggy | 1.6.0 | `pluggy-1.6.0-py3-none-any.whl` | MIT | Declared license; wheel `LICENSE` captured, text SHA-256 above | APPROVE_WITH_CONDITION | Retain the copyright and permission notice on redistribution. |
| psycopg | 3.3.5 | `psycopg-3.3.5-py3-none-any.whl` | LGPL-3.0-only | SPDX expression and embedded LGPL v3 `LICENSE.txt`; exact text reviewed below | EXTERNAL_LEGAL_REVIEW_REQUIRED | Wheel evidence states conditional conveying, combined-work, modification, and source terms, but does not establish their application to the intended deployment and distribution. |
| psycopg-binary | 3.3.5 | `psycopg_binary-3.3.5-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.whl` | LGPL-3.0-only (package metadata); bundled components not individually identified by license | SPDX expression, embedded LGPL v3 `LICENSE.txt`, and native payload inventory reviewed below | EXTERNAL_LEGAL_REVIEW_REQUIRED | Native libraries are bundled without component-specific license/source evidence in this wheel; their redistribution obligations and the LGPL combined-work path require external review. |
| pygments | 2.21.0 | `pygments-2.21.0-py3-none-any.whl` | BSD-2-Clause | SPDX expression; wheel license file/hash recorded above | APPROVE_WITH_CONDITION | Retain copyright/license/disclaimer on redistribution. |
| pytest | 9.1.1 | `pytest-9.1.1-py3-none-any.whl` | MIT | SPDX expression; wheel license file/hash recorded above | APPROVE_WITH_CONDITION | Retain the copyright and permission notice on redistribution. |
| pytest-django | 4.14.0 | `pytest_django-4.14.0-py3-none-any.whl` | BSD-3-Clause, including fork notice | Declared license text in packet includes both pytest-django and Ben Firshman fork notices; wheel text SHA-256 above | APPROVE_WITH_CONDITION | Preserve both copyright/license/disclaimer notices and the non-endorsement condition on redistribution. |
| python-dotenv | 1.2.3 | `python_dotenv-1.2.3-py3-none-any.whl` | BSD-3-Clause | Declared license; wheel license file/hash recorded above | APPROVE_WITH_CONDITION | Retain copyright/license/disclaimer on redistribution. |
| ruff | 0.16.5 | `ruff-0.16.5-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl` | MIT | SPDX expression; wheel license file/hash recorded above | APPROVE_WITH_CONDITION | Retain the copyright and permission notice on redistribution. |
| sqlparse | 0.6.0 | `sqlparse-0.6.0-py3-none-any.whl` | BSD-3-Clause terms in wheel text (no SPDX expression) | BSD classifier and embedded `AUTHORS`/`LICENSE`; exact text reviewed below | EVIDENCE_SUFFICIENT_FOR_PRODUCT_OWNER_DECISION | The three redistribution conditions are explicit in the wheel license; Product Owner disposition remains unrecorded. |
| typing-extensions | 4.16.0 | `typing_extensions-4.16.0-py3-none-any.whl` | PSF-2.0 | SPDX expression; wheel license file/hash recorded above | APPROVE_WITH_CONDITION | Retain the exact PSF license and attribution text on redistribution. |
| tzdata | 2026.5 | `tzdata-2026.5-py2.py3-none-any.whl` | Apache-2.0 | Declared license; wheel `LICENSE` and `LICENSE_APACHE` captured, combined text SHA-256 above | APPROVE_WITH_CONDITION | Retain applicable license, copyright, and any notice text on redistribution. |

## Evidence closure for the four previously unresolved exact artifacts

This section records wheel evidence only. The classifications identify whether the evidence was sufficient for a Product Owner **decision**, not whether the gate may pass. The hashes in the inventory above were verified against the four local development wheels in `output/cep-013/artifacts/dev/`. The matching production Psycopg and sqlparse wheel filenames are recorded in the production inventory. No use, modification, or external distribution fact is inferred from a wheel's presence in the build inventory.

### colorama 0.4.6 — `colorama-0.4.6-py2.py3-none-any.whl`

`METADATA` has a generic BSD classifier and `License-File: LICENSE.txt`, but no SPDX expression. The embedded `colorama-0.4.6.dist-info/licenses/LICENSE.txt` (SHA-256 `cac35c02686e5d04a5a7140bfb3b36e73aed496656e891102e428886d7930318`) contains the three-clause BSD text and copyright `(c) 2010 Jonathan Hartley`; the detected terms are **BSD-3-Clause** by the text itself. It permits source and binary redistribution, with or without modification. Source redistribution must retain the copyright notice, conditions, and disclaimer. Binary redistribution, including a wheel or image if distributed, must reproduce them in documentation and/or other distribution materials. The names of copyright holders/contributors may not endorse derived products without prior written permission. The text states no source-availability or modification-notice requirement. It does not state a redistribution obligation for private internal use; no deployment conclusion is drawn.

**Classification:** `EVIDENCE_SUFFICIENT_FOR_PRODUCT_OWNER_DECISION`.

### psycopg 3.3.5 — `psycopg-3.3.5-py3-none-any.whl`

`METADATA` declares `License-Expression: LGPL-3.0-only` and `License-File: LICENSE.txt`. The embedded LGPL v3 text has SHA-256 `e3a994d82e644b03a792a930f574002658412f62407f5fee083f2555c5f23118`; it says it incorporates GNU GPL v3 terms. The wheel has Python source files and no native `.so` files. It contains the LGPL document, but no separate GNU GPL v3 text or source-offer statement was identified among its license-like files.

- **Library use/internal use:** LGPL text defines an Application using a Library interface and a Combined Work. Its stated conditions in sections 2–5 concern *conveying*; the wheel does not establish whether private use or any particular SaaS deployment conveys the library.
- **Redistribution of wheel/container:** If conveying a Combined Work, LGPL section 4 states prominent library/license notice, copies of the GNU GPL and LGPL documents, applicable displayed copyright notice, and either the specified source/application-code path or a suitable shared-library mechanism. Sections 3 and 5 state additional conditions for their specified object-code/combined-library cases. Whether distribution of this wheel or an image fits those cases is not established here.
- **Bundled binary components:** No native shared objects were found in this wheel; this says nothing about separately installed components.
- **Modification:** Section 2 specifies conditions for conveying certain modified Library versions; the incorporated GPL terms may add applicable requirements. No modification of this exact wheel is evidenced.
- **Source availability:** The wheel includes its Python files. LGPL section 4 describes Minimal Corresponding Source and Corresponding Application Code for one Combined Work option; the evidence does not establish that this option applies or that all corresponding source/materials are available for the intended distribution.

**Classification:** `EXTERNAL_LEGAL_REVIEW_REQUIRED` because the applicable conveying/combined-work path and incorporated GPL requirements cannot be determined from the current wheel and deployment evidence.

### psycopg-binary 3.3.5 — `psycopg_binary-3.3.5-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.whl`

`METADATA` declares `License-Expression: LGPL-3.0-only` and `License-File: LICENSE.txt`. Its embedded LGPL v3 text is byte-identical to the psycopg license above (SHA-256 `e3a994d82e644b03a792a930f574002658412f62407f5fee083f2555c5f23118`). The wheel contains two `psycopg_binary/*.so` modules and 15 shared libraries in `psycopg_binary.libs/`, including `libpq`, `libssl`, `libcrypto`, Kerberos, LDAP, SASL, and related libraries. Its only license-like file is the package `LICENSE.txt`; the wheel does not identify a license, notice set, corresponding source, or source offer separately for those bundled libraries.

- **Library use/internal use:** The embedded LGPL text defines Library/Application/Combined Work and sets conditions for conveying. It does not establish that private internal use conveys the package or native components.
- **Redistribution of wheel/container:** The embedded LGPL section 4 has the notice, license-copy, conditional copyright-display, and source/relinking or shared-library-mechanism terms described for psycopg above. A redistributed wheel or image would also carry the native libraries; their own license terms and required notices are not established by this wheel.
- **Bundled binary components:** The 15 `.libs/` objects are observable, but filename alone does not prove each component's license, build provenance, linkage behavior, or distribution obligations. The wheel's `LGPL-3.0-only` package expression is not evidence that every bundled component has that license.
- **Modification:** LGPL section 2 addresses conveying certain modified Library versions; no modification is evidenced. Obligations for modifying the bundled native libraries cannot be stated from their missing component-specific terms.
- **Source availability:** This wheel provides compiled native objects; no component-specific source bundles, source offers, or corresponding-source evidence were identified. LGPL section 4 describes a conditional source/relinking path, but current evidence does not establish which path applies or how it would be fulfilled.

**Classification:** `EXTERNAL_LEGAL_REVIEW_REQUIRED` for the LGPL application and the unverified bundled-component licenses, notices, and source obligations.

### sqlparse 0.6.0 — `sqlparse-0.6.0-py3-none-any.whl`

`METADATA` has a generic BSD classifier and `License-File: AUTHORS`/`LICENSE`, but no SPDX expression. The embedded `sqlparse-0.6.0.dist-info/licenses/LICENSE` (SHA-256 of that file `c1938235b80d39e93138eae89edc3af67e18ecbc40d266529fa57b2dce426310`) contains three-clause BSD text and copyright `(c) 2016, Andi Albrecht`; `AUTHORS` is also included. Source redistribution must retain copyright, conditions, and disclaimer; binary redistribution, including a wheel or image if distributed, must reproduce them in documentation and/or other materials. Author/contributor names may not endorse a derived product without prior written permission. The text permits modification and states no source-availability or modification-notice requirement. It does not state a redistribution obligation for private internal use; no deployment conclusion is drawn.

**Classification:** `EVIDENCE_SUFFICIENT_FOR_PRODUCT_OWNER_DECISION`.

**Open external legal review:** 2 exact artifacts: `psycopg-3.3.5-py3-none-any.whl` and `psycopg_binary-3.3.5-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.whl`.

## Product Owner decision — 2026-10-15

The BONIRA Product Owner approved the 12 exact wheels marked `APPROVE_WITH_CONDITION` in the table above, limited to their recorded wheel SHA-256 digests and stated notice/license conditions. The Product Owner also approved `colorama-0.4.6-py2.py3-none-any.whl` (SHA-256 `4f1d9991f5acc0ca119f9d443620b77f9d6b33703e51011c16baf57afb285fc6`) and `sqlparse-0.6.0-py3-none-any.whl` (SHA-256 `b861c0288ce2fa56209a9a6412d2e066ac664b3873b89c26c9d8415e8e32996f`) with these conditions: retain applicable copyright notices, BSD-3-Clause terms and disclaimer, and include the required notices/materials when redistributing the exact artifact or an image containing it. Approval does not extend to other versions or artifacts.

**Approval count:** 14 exact artifacts. **Unapproved:** `psycopg-3.3.5-py3-none-any.whl` and `psycopg_binary-3.3.5-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.whl` remain `EXTERNAL_LEGAL_REVIEW_REQUIRED`; see `CEP-013_PSYCO_PG_LEGAL_REVIEW_PACKET.md`. No legal determination or `ALLOW` entry for those two is recorded. The license gate remains BLOCKED.

**CEP-013:** EXECUTION PARTIAL; AC-01 and scoped DoD remain open. `ROADMAP.md` was checked and its CEP-013 partial status and license-disposition dependency remain current.

## Final Linux-set disposition — 2026-10-16

Human Decision Maker approved removal of `psycopg-binary==3.3.5` from both CEP-013 Linux sets and retained exact pure `psycopg==3.3.5` (wheel SHA-256 `ce5aa5cdb4f9379f00f487590e5890bfa7df9a164648c969ffa628505e21af4e`) under its existing `APPROVE_WITH_CONDITION` disposition. No LGPL terms are reinterpreted here. The exact binary wheel remains rejected and is not included in the approved Linux sets. The historical Windows lock and shared requirement declaration are unchanged. All 15 remaining exact artifacts have machine-readable dispositions; the local `output/cep-013/final-gate/gate-result.json` records `licenses=PASS`. This opens the CEP-013 **license gate only**; it does not authorize production release or complete the separate attestation requirement.
