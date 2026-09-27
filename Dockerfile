# Production image: Odoo 19 with the workshop modules. Configuration comes from the environment (deploy/entrypoint.sh).
FROM odoo:19.0

USER root
# Not /mnt/extra-addons: the base image declares it a volume, and a recreated container would keep
# the previous release's modules in it instead of the ones in this image.
COPY workshop_os /opt/oficina/addons/workshop_os
COPY l10n_br_nfse_nacional /opt/oficina/addons/l10n_br_nfse_nacional
COPY workshop_os_nfse /opt/oficina/addons/workshop_os_nfse
COPY deploy/entrypoint.sh deploy/placeholder.py /deploy/
# Fingerprint of the addons: the entrypoint upgrades the modules only when it changes.
RUN chmod 755 /deploy/entrypoint.sh \
    && cd /opt/oficina/addons \
    && find . -type f ! -name '*.pyc' -print0 | sort -z | xargs -0 sha1sum | sha1sum | cut -c1-40 > /deploy/addons.sha
USER odoo

ENTRYPOINT ["/deploy/entrypoint.sh"]
