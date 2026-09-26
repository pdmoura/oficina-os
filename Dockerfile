# Production image: Odoo 19 with the workshop modules. Configuration comes from the environment (deploy/entrypoint.sh).
FROM odoo:19.0

USER root
COPY workshop_os /mnt/extra-addons/workshop_os
COPY l10n_br_nfse_nacional /mnt/extra-addons/l10n_br_nfse_nacional
COPY workshop_os_nfse /mnt/extra-addons/workshop_os_nfse
COPY deploy/entrypoint.sh /deploy/entrypoint.sh
# Fingerprint of the addons: the entrypoint upgrades the modules only when it changes.
RUN chmod 755 /deploy/entrypoint.sh \
    && cd /mnt/extra-addons \
    && find . -type f ! -name '*.pyc' -print0 | sort -z | xargs -0 sha1sum | sha1sum | cut -c1-40 > /deploy/addons.sha
USER odoo

ENTRYPOINT ["/deploy/entrypoint.sh"]
