# Laravel API (PHP-FPM) on Ubuntu 24.04, which ships PHP 8.3.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    COMPOSER_ALLOW_SUPERUSER=1 \
    COMPOSER_NO_INTERACTION=1

# Optional extra CA certificates (for TLS-intercepting proxies): docker/certs/*.crt
COPY docker/certs/ /usr/local/share/ca-certificates/extra/

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl unzip git \
      php8.3-fpm php8.3-cli php8.3-pgsql php8.3-sqlite3 php8.3-mbstring php8.3-xml php8.3-curl php8.3-zip php8.3-intl php8.3-bcmath \
      postgresql-client \
 && update-ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && sed -i 's|^listen = .*|listen = 9000|; s|^;clear_env = no|clear_env = no|; s|^;catch_workers_output = yes|catch_workers_output = yes|' /etc/php/8.3/fpm/pool.d/www.conf \
 && sed -i 's|^;*error_log = .*|error_log = /proc/self/fd/2|' /etc/php/8.3/fpm/php-fpm.conf \
 && sed -i 's|^post_max_size = .*|post_max_size = 8M|' /etc/php/8.3/fpm/php.ini \
 && mkdir -p /run/php

COPY --from=composer:2 /usr/bin/composer /usr/bin/composer

WORKDIR /var/www/backend
COPY backend/composer.json backend/composer.lock ./
RUN composer install --no-dev --no-scripts --no-autoloader --prefer-dist

COPY backend/ ./
RUN rm -f .env \
 && composer dump-autoload --optimize --no-dev \
 && mkdir -p storage/framework/cache storage/framework/views storage/framework/sessions storage/logs bootstrap/cache \
 && chown -R www-data:www-data storage bootstrap/cache

COPY docker/php/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 9000
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["php-fpm8.3", "-F"]
