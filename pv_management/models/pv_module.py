from odoo import models, fields, api ,_
from odoo.exceptions import ValidationError

class MarqueOnduleur(models.Model):
    _name = 'marque.onduleur'
    _description = 'Marque Onduleur'

    name = fields.Char(string='Nom', required=True, translate=True)
    code = fields.Char(string='Code', translate=True)


class PVModule(models.Model):
    _name = 'pv.module'
    _description = 'PV Module'
    _rec='reference'


    # Change reference field to be a sequence with readonly and default value
    reference = fields.Char(string='Reference Module PV',  default=lambda self: _('New'),
       copy=False, readonly=True, tracking=True, required=True)

    @api.constrains('reference')
    def _check_unique_reference(self):
        for record in self:
            if record.reference:
                # Search for other records with the same reference
                duplicates = self.search([
                    ('reference', '=', record.reference),
                    ('id', '!=', record.id)
                ])
                if duplicates:
                    raise ValidationError("La référence doit être unique. Une autre entrée utilise déjà cette")

    brand = fields.Many2one('marque.onduleur', string='Marque Onduleur')
    power = fields.Char(string='Puissance Module PV (WC)')

    # Add create method to handle sequence generation
    @api.model
    def create(self, vals):
        if vals.get('reference', 'New') == 'New':
            vals['reference'] = self.env['ir.sequence'].next_by_code('pv.module.sequence') or 'New'
        return super(PVModule, self).create(vals)

    def name_get(self):
        result = []
        for module in self:
            brand_name = module.brand.name if module.brand else ''
            power = module.power or ''
            name = f"{module.reference} - {brand_name} {power}"
            result.append((module.id, name))
        return result