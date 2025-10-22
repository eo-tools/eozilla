# DTE-S2GOS application example

Build and run the image

```commandline
cd ..
docker build -f procodile-example/Dockerfile -t procodile-example-v1 .
docker run procodile-example-v1 procodile-example --help
docker run -it procodile-example-v1 /bin/bash
```
