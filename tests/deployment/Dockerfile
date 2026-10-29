ARG MONITOR_IMAGE=geo-monitor-monitor
FROM docker:29-cli AS docker
FROM ${MONITOR_IMAGE}
USER root
COPY --from=docker /usr/local/bin/docker /usr/local/bin/docker-real
COPY --from=docker /usr/local/libexec/docker/cli-plugins/ /usr/local/libexec/docker/cli-plugins/
RUN apt-get update && apt-get install -y --no-install-recommends curl openssl && rm -rf /var/lib/apt/lists/*
COPY acceptance.py docker_wrapper.py /acceptance-tests/
ENTRYPOINT ["python", "/acceptance-tests/acceptance.py"]
CMD []
