# Container build and trust

The Docker image builds the installed Python service together with Ubuntu's
matching GI and D-Bus bindings. CI builds the real image and checks its imports
with `docker run --network none`. These checks do not connect to MQTT or a live
Venus OS D-Bus, and do not qualify hardware or device deployment.

## HTTPS package bootstrap

The digest-pinned minimal Ubuntu 24.04 image does not provide the CA bundle needed
to bootstrap HTTPS package installation. An earlier HTTP-only path failed when
the hosted runner could not reach Ubuntu's HTTP endpoint. Increasing the timeout
would not remove that dependency.

1. BuildKit downloads the dated Mozilla PEM bundle published by curl over HTTPS,
   using the builder's trust store. `ADD --checksum` verifies its SHA-256 before
   it becomes a build input.
2. A scratch stage holds that bundle with mode `0644`, so Ubuntu's `_apt` sandbox
   can read it. Each package-install step receives it through a read-only bind
   mount at `/tmp/apt-bootstrap-ca.pem`.
3. The installer selects signed Ubuntu Noble indexes: the Canonical archive and an
   independently operated Kernel.org fallback for amd64, and the official ports
   archive for other architectures.
   All URLs use HTTPS. `Signed-By` still requires Ubuntu's archive keyring.
4. Only those APT invocations use the mounted bundle through
   `Acquire::https::CAInfo`. Installation includes Ubuntu's `ca-certificates`
   package, which supplies the ordinary trust store for later build steps and
   runtime use. The bootstrap mount disappears at the end of each `RUN` and is
   not copied into the final image.

TLS peer and hostname verification remain enabled. Package signature checks,
strict index-update failure, two retries, 20-second transport timeouts, a
60-second lock timeout, and the 180/360-second update/install deadlines remain
in force. Temporary indexes are removed on success or failure.

The amd64 list prefers `https://archive.ubuntu.com/ubuntu/` and falls back to
`https://mirrors.kernel.org/ubuntu/`. Archive and security hostnames at Canonical
can share a backend; a second name did not prevent the observed index-download
timeouts. The [Linux Kernel Archives](https://mirrors.kernel.org/) operates the
second service, whose archive is listed in [Ubuntu's official mirror registry](https://launchpad.net/ubuntu/+mirror/mirrors.us.kernel.org-archive).
Use its current HTTPS endpoint, not the registry's legacy hostname, whose TLS
certificate does not cover that name. Both endpoints supply all four Noble
suites and remain subject to the same Ubuntu archive-keyring checks. Before
changing the mirror list, check the operator, registry, certificate and suite
availability with the pinned CA bundle, then run the real container build and
offline import checks. A successful local request alone does not establish
availability from a hosted runner.

The Dockerfile requires BuildKit with Dockerfile syntax support for
[`ADD --checksum`](https://docs.docker.com/reference/dockerfile/#add---checksum)
(1.6 or newer) and `RUN --mount`; CI uses the runner's Docker BuildKit. No host
certificate files, credentials, or additional CA image are required.

## Maintaining the CA input

The current bootstrap input is
[`cacert-2026-10-20.pem`](https://curl.se/ca/cacert-2026-10-20.pem), with SHA-256
`796f1389bfea13c0ed78f663b765baaff54a508e5483786bd6ece73c5e3e3cbe`.
It is a conversion of Mozilla's CA data, licensed under MPL-2.0; the original
notice is retained in the unmodified PEM. It contains certificate trust anchors,
not the complete Firefox trust policy or its browser-specific name constraints.
See curl's [CA extraction documentation](https://curl.se/docs/caextract.html).

Review this pin during dependency maintenance and promptly after relevant CA
removal, expiry, or trust incidents. Compare the dated bundle and its published
SHA-256 on curl's official site, inspect the trust-store change, then update the
dated URL and digest together in the Dockerfile and its contract test. Do not
replace the URL with the moving `cacert.pem` or disable TLS to bypass a failure.
Run `pytest tests/test_container_apt.py`, then require the real image build and
offline native-import CI checks before merging. A pin freezes trust additions
and removals until that reviewed update is made.
