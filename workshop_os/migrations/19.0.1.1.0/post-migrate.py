def migrate(cr, version):
    """Databases installed before 1.1 kept Odoo's open self sign-up: close it once, like new installs."""
    cr.execute(
        "UPDATE ir_config_parameter SET value = 'b2b' "
        "WHERE key = 'auth_signup.invitation_scope' AND value = 'b2c'"
    )
