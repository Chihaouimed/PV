from odoo import models, fields, api

class FicheReponse(models.Model):
    _name = 'fiche.reponse'
    _description = 'Fiche de Réponse'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    
    name = fields.Char(string='Référence', required=True, copy=False, readonly=True,
                      default=lambda self: self.env['ir.sequence'].next_by_code('fiche.reponse.sequence') or 'Nouveau')
    intervention_id = fields.Many2one('fiche.intervention', string='Intervention', required=True, readonly=True)
    date_cloture = fields.Datetime(string='Date de Clôture', required=True, default=fields.Datetime.now)
    equipe_intervention_ids = fields.Many2many(related='intervention_id.equipe_intervention_ids', string='Équipe d\'Intervention')
    montant_a_payer = fields.Float(string='Montant à Payer', digits=(10, 2))
    est_paye = fields.Selection([
        ('oui', 'Oui'),
        ('non', 'Non')
    ], string='Payé', default='non', tracking=True)
    
    # Champs liés à l'intervention
    installation_id = fields.Many2one(related='intervention_id.installation_id', string='Installation', readonly=True)
    type_intervention = fields.Selection(related='intervention_id.type_intervention', string='Type d\'intervention', readonly=True)
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'Nouveau') == 'Nouveau':
            vals['name'] = self.env['ir.sequence'].next_by_code('fiche.reponse.sequence') or 'Nouveau'
        return super(FicheReponse, self).create(vals)
        
    def action_view_intervention(self):
        """Bouton pour voir la fiche d'intervention liée"""
        self.ensure_one()
        return {
            'name': 'Intervention',
            'view_mode': 'form',
            'res_model': 'fiche.intervention',
            'res_id': self.intervention_id.id,
            'type': 'ir.actions.act_window',
        }
