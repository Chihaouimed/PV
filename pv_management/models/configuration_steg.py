from odoo import fields , models ,api

class ConfigurationDistrictSteg(models.Model):
    _name = 'configuration.district.steg'
    _description = 'Configuration District STEG'

    name = fields.Char(string='Nom', required=True)
    marque_onduleur = fields.Many2one('marque.onduleur', string='Marque Onduleur')
    mo = fields.Char(related='marque_onduleur.name', string='Marque Onduleur', readonly=True)
