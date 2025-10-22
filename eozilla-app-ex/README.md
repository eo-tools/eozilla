# DTE-S2GOS application example

Build and run the image

```commandline
cd ..
docker build -f eozilla-app-ex/Dockerfile -t eozilla-app-ex-v1 .
docker run eozilla-app-ex-v1 eozilla-app-ex --help
docker run -it eozilla-app-ex-v1 /bin/bash
```
