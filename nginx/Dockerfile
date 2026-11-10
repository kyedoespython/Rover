FROM nginx:alpine

RUN apk add --no-cache openssl

COPY nginx/nginx.conf /etc/nginx/nginx.conf
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY nginx/start-nginx.sh /usr/local/bin/start-nginx

RUN chmod 0755 /usr/local/bin/start-nginx \
    && mkdir -p /run/nginx /etc/nginx/certs

ENTRYPOINT ["/usr/local/bin/start-nginx"]
CMD ["nginx", "-g", "daemon off;"]
