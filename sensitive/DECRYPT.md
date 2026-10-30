# sensitive/ — encrypted harvest archive (PUBLIC ciphertext)

`harvest.tar.gpg.part-*` = the raw harvest store (595 files), tar'd and
encrypted with GPG symmetric AES-256. Ciphertext is public; the key is
owner-held only (never in any repo). Plaintext sha256 in HARVEST-SHA256.txt
(of the .gpg file).

Restore:
    cat harvest.tar.gpg.part-* > harvest.tar.gpg
    gpg -d harvest.tar.gpg | tar -xf -
