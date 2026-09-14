# Third-party notices

FIT File & Merger uses components from the FIT File Faker project. The merge, verification,
upload policy, recovery and cleanup layers documented in this package are separate
extensions. FIT File & Merger is an independent work and is not affiliated with, sponsored
by, or endorsed by the FIT File Faker project or its author.

## FIT File Faker

| Field | Value |
|-------|-------|
| Package | `fit-file-faker` (PyPI) |
| Version pinned and tested | 2.1.5 |
| Author | Joshua Taillon |
| Project | https://github.com/jat255/Fit-File-Faker |
| Release | https://github.com/jat255/Fit-File-Faker/releases/tag/v2.1.5 |
| Tag commit | `bdbeb1d83f5806950dd00c8c0ba755264a7448c9` |
| Licence | MIT, reproduced in full below |

The installation this documentation describes is the published distribution, not a fork and
not a source checkout. No upstream file is modified. One parser behaviour is adjusted at
runtime, inside this project's own process, so that a valid nul-terminated string followed by
non-UTF-8 padding does not abort parsing; the installed package is left untouched.

What is used from it:

- the vendored `fit_tool` library, for reading, building and writing FIT files;
- its profile configuration format, which holds the upload credentials;
- its command line interface, as the upload fallback for files this pipeline did not handle
  itself, and for identity rewriting of files that need no merge.

Record the tested version whenever this is redeployed. FIT semantics, vendored profile
coverage and upload behaviour are all version-sensitive, and the exact field counts this
pipeline verifies against depend on them.

### FIT File Faker licence

```
Copyright 2024-2026, Joshua Taillon

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```

## fit_tool

The `fit_file_faker/vendor/fit_tool` directory within the above distribution carries its own
licence, reproduced below. It is retained separately here because it is a distinct grant with
its own conditions, including an endorsement restriction, and is not covered by the MIT
notice above.

Source: https://github.com/jat255/Fit-File-Faker/blob/v2.1.5/fit_file_faker/vendor/fit_tool/LICENSE

### fit_tool licence

```
Copyright 2021 Stages Cycling. All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

    * Redistributions of source code must retain the above copyright
      notice, this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above
      copyright notice, this list of conditions and the following
      disclaimer in the documentation and/or other materials provided
      with the distribution.
    * Neither the name of Stages Cycling nor the names of its
      contributors may be used to endorse or promote products derived
      from this software without specific prior written permission.

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
```

## Trademarks

Garmin, Tacx, Edge, Zwift, BikeTerra, Strava and Intervals.icu are the marks of their
respective owners. They appear here only to describe interoperability. No affiliation or
endorsement is claimed or implied.
