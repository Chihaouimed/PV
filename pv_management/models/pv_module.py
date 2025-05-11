from odoo import models, fields, api


class PVModule(models.Model):
    _name = 'pv.module'
    _description = 'PV Module'


    # Change reference field to be a sequence with readonly and default value
    reference = fields.Char(string='Reference Module PV', required=True, readonly=True, copy=False,
                            default=lambda self: self.env['ir.sequence'].next_by_code('pv.module.sequence') or 'New')
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