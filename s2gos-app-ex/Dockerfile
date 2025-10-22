# Stage 1 ---------------------------
FROM ghcr.io/prefix-dev/pixi:0.50.2-bookworm-slim AS build
WORKDIR /app
RUN mkdir gavicore
RUN mkdir s2gos-app-ex
COPY ./gavicore ./gavicore
COPY ./s2gos-app-ex ./s2gos-app-ex
RUN cd ./s2gos-app-ex && pixi install --locked -e production
RUN cd ./s2gos-app-ex && pixi shell-hook -e production -s bash > /shell-hook
RUN echo "#!/bin/bash" > /app/entrypoint.sh
RUN cat /shell-hook >> /app/entrypoint.sh
RUN echo 'exec "$@"' >> /app/entrypoint.sh

# Stage 2 ---------------------------
FROM ubuntu:24.04 AS production
WORKDIR /app
COPY --from=build /app/s2gos-app-ex/.pixi/envs/production /app/s2gos-app-ex/.pixi/envs/production
COPY --from=build /app/gavicore/src /app/gavicore/src
COPY --from=build /app/s2gos-app-ex/src /app/s2gos-app-ex/src
COPY --from=build --chmod=0755 /app/entrypoint.sh /app/entrypoint.sh
ENTRYPOINT [ "/app/entrypoint.sh" ]
