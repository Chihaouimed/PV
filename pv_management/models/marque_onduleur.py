from odoo import models, fields, api

class MarqueOnduleur(models.Model):
    _name = 'marque.onduleur'
    _description = 'Marque Onduleur'

    name = fields.Char(string='Nom', required=True, translate=True)
    code = fields.Char(string='Code', translate=True)