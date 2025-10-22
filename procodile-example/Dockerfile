# Stage 1 ---------------------------
FROM ghcr.io/prefix-dev/pixi:0.50.2-bookworm-slim AS build
WORKDIR /app
RUN mkdir gavicore
RUN mkdir procodile-example
COPY ./gavicore ./gavicore
COPY ./procodile-example ./procodile-example
RUN cd ./procodile-example && pixi install --locked -e production
RUN cd ./procodile-example && pixi shell-hook -e production -s bash > /shell-hook
RUN echo "#!/bin/bash" > /app/entrypoint.sh
RUN cat /shell-hook >> /app/entrypoint.sh
RUN echo 'exec "$@"' >> /app/entrypoint.sh

# Stage 2 ---------------------------
FROM ubuntu:24.04 AS production
WORKDIR /app
COPY --from=build /app/procodile-example/.pixi/envs/production /app/procodile-example/.pixi/envs/production
COPY --from=build /app/gavicore/src /app/gavicore/src
COPY --from=build /app/procodile-example/src /app/procodile-example/src
COPY --from=build --chmod=0755 /app/entrypoint.sh /app/entrypoint.sh
ENTRYPOINT [ "/app/entrypoint.sh" ]
