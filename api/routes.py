from api.modules import attestations
from api.modules import notifications
from api.modules import linker


def add_resources(api, resources, namespace):
    for path, resource in resources.items():
        api.add_resource(resource, namespace + path)


def init_routes(api):
    # add routes for new modules here
    add_resources(api, attestations.resources, '/api/attestations/')
    add_resources(api, notifications.resources, '/api/notifications/')
    add_resources(api, linker.resources, '/api/wallet-linker/')
