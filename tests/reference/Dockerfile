# Temporary upstream oracle; never copied into the Python runtime.
FROM node:26-alpine@sha256:40cd011b55415bc894e45b02fdd5a5dfde056921b7d23a64c74f80497af48797
RUN apk add --no-cache git ca-certificates
WORKDIR /reference
RUN git init -q \
    && git remote add upstream https://github.com/timo-reymann/mealie-mcp-server.git \
    && git fetch --quiet upstream d027e1b4a314d781a322f1f91e37840f01464d77 \
    && git checkout --detach FETCH_HEAD \
    && npm install --global yarn@1.22.22 \
    && yarn install --frozen-lockfile --ignore-scripts \
    && yarn build
CMD ["yarn", "test"]
