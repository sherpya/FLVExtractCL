#!/bin/sh
# builds standalone program

mkdir -p /tmp/$$-build
find . -name \*.py | cpio -pdm /tmp/$$-build
( cd /tmp/$$-build && zip -9qr /tmp/$$-build.zip * )

echo '#!/usr/bin/env python' > flvextract
cat /tmp/$$-build.zip >> flvextract
chmod 755 flvextract
ls -l flvextract

rm -fr /tmp/$$-build
rm -f /tmp/$$-build.zip
