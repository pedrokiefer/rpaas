# Copyright 2015 rpaas authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import consul

from . import nginx

ACL_TEMPLATE = """key "{service_name}/{instance_name}" {{
    policy = "read"
}}

key "{service_name}/{instance_name}/status" {{
    policy = "write"
}}

service "nginx" {{
    policy = "write"
}}
"""


class ConsulManager(object):

    def __init__(self, config):
        host = config.get("CONSUL_HOST")
        port = int(config.get("CONSUL_PORT", "8500"))
        token = config.get("CONSUL_TOKEN")
        self.client = consul.Consul(host=host, port=port, token=token)
        self.config_manager = nginx.ConfigManager(config)
        self.service_name = config.get("RPAAS_SERVICE_NAME", "rpaas")

    def generate_token(self, instance_name):
        rules = ACL_TEMPLATE.format(service_name=self.service_name,
                                    instance_name=instance_name)
        acl_name = "{}/{}/token".format(self.service_name, instance_name)
        return self.client.acl.create(name=acl_name, rules=rules)

    def destroy_token(self, acl_id):
        self.client.acl.destroy(acl_id)

    def destroy_instance(self, instance_name):
        self.client.kv.delete(self._key(instance_name), recurse=True)

    def write_healthcheck(self, instance_name):
        self.client.kv.put(self._key(instance_name, "healthcheck"), "true")

    def remove_healthcheck(self, instance_name):
        self.client.kv.delete(self._key(instance_name, "healthcheck"))

    def write_location(self, instance_name, path, destination=None, content=None):
        if content:
            content = content.strip()
        else:
            content = self.config_manager.generate_host_config(path, destination)
        self.client.kv.put(self._location_key(instance_name, path), content)

    def remove_location(self, instance_name, path):
        self.client.kv.delete(self._location_key(instance_name, path))

    def write_block(self, instance_name, block_name, content):
        content = content.strip()
        self.client.kv.put(self._block_key(instance_name, block_name), content)

    def get_certificate(self, instance_name):
        cert = self.client.kv.get(self._ssl_cert_key(instance_name))[1]
        key = self.client.kv.get(self._ssl_key_key(instance_name))[1]
        if not cert or not key:
            raise ValueError("certificate not defined")
        return cert["Value"], key["Value"]

    def set_certificate(self, instance_name, cert_data, key_data):
        self.client.kv.put(self._ssl_cert_key(instance_name), cert_data.replace("\r\n", "\n"))
        self.client.kv.put(self._ssl_key_key(instance_name), key_data.replace("\r\n", "\n"))

    def _ssl_cert_key(self, instance_name):
        return self._key(instance_name, "ssl/cert")

    def _ssl_key_key(self, instance_name):
        return self._key(instance_name, "ssl/key")

    def _location_key(self, instance_name, path):
        location_key = "ROOT"
        if path != "/":
            location_key = path.replace("/", "___")
        return self._key(instance_name, "locations/" + location_key)

    def _block_key(self, instance_name, block_name):
        block_key = "ROOT"
        return self._key(instance_name, "blocks/%s/%s" % (block_name,
                                                          block_key))

    def _key(self, instance_name, suffix=None):
        key = "{}/{}".format(self.service_name, instance_name)
        if suffix:
            key += "/" + suffix
        return key
