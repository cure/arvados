#!/bin/bash

if [[ "$1" == "" ]]; then
  echo "Syntax: $0 <package=version> [package=version] ..."
  exit 1
fi

if [[ "$@" =~ "arvados-workbench=" ]] || [[ "$@" =~ "arvados-sso-server=" ]] || [[ "$@" =~ "arvados-api-server=" ]]; then
  RESET_NGINX_DAEMON_FLAG=true
else
  RESET_NGINX_DAEMON_FLAG=false
fi

if [[ "$RESET_NGINX_DAEMON_FLAG" == true ]]; then
  # our packages restart nginx; with the 'daemon off' flag in place, 
  # that makes package install hang. Arguably we shouldn't be restarting nginx on install.
  sed -i 's/daemon off;/#daemon off;/' /etc/nginx/nginx.conf
fi

apt-get -qqy install $@

if [[ "$RESET_NGINX_DAEMON_FLAG" == true ]]; then
  /etc/init.d/nginx stop
  sed -i 's/#daemon off;/daemon off;/' /etc/nginx/nginx.conf
fi
