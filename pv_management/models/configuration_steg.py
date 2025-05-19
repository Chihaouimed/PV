from odoo import fields , models ,api

class Calibredisj(models.Model):
    _name = 'calibre.disj'
    _description = 'Calibre Disjoncteur'

    name = fields.Char(string='Nom', required=True, translate=True)
    code = fields.Char(string='Intensité', translate=True)


class ConfigurationDistrictSteg(models.Model):
    _name = 'configuration.district.steg'
    _description = 'Configuration District STEG'

    name = fields.Char(string='Nom', required=True)

