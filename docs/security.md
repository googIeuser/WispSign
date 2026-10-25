# Security boundaries

Certificate files and provisioning profiles are stored locally. Saved passwords are
protected with Windows DPAPI for the current Windows user. This does not protect against
malware running as that user or an administrator.

The bundled zsign tool receives the certificate password in its process arguments while
signing. A local process with sufficient access can inspect those arguments. Error output
redacts the password, but that does not hide it from operating-system process inspection.
Use a dedicated signing password rather than reusing an account password.

Certificate import compares SHA-256 fingerprints of the complete certificates, rather than
serial numbers alone. A device absent from a profile is allowed only when the profile has
an explicit `ProvisionsAllDevices` flag. An empty device list alone grants no permission.

Profile metadata parsing does not authenticate Apple's CMS signature, validate Apple's
certificate chain, or check revocation online. Post-sign checks inspect resource hashes and
the main app's XML identity and push entitlements; they are not a complete Apple code-signing
verifier. The device must still accept the app. A real-device test is required before
claiming installation or push delivery works; see [the test procedure](device-test.md).

Repository JSON is limited to 5 MB and IPA downloads to 4 GB, including when a server omits
or misstates Content-Length. Unsafe archive paths, symlinks and extraction beyond the
uncompressed size limit are rejected.

Documentation screenshots use only the mock backend. The visible demo label, `DEMO-DEVICE`,
`DEMO-OTHER-DEVICE` and `DEMO-TEAM-*` values identify fictional records. No real signing
files, device records or application data are needed to capture them.
