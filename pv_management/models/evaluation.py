from odoo import models, fields, api


class Evaluation(models.Model):
    _name = 'pv.evaluation'
    _description = 'PV Installation and Technician Evaluation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True,
                       default=lambda self: self.env['ir.sequence'].next_by_code('pv.evaluation.sequence') or 'New')

    # Add client field to allow filtering installations by client
    client_id = fields.Many2one('res.partner', string='Client')
    installation_id = fields.Many2one('pv.installation', string='Installation', required=True,
                                      domain="[('client', '=', client_id)]")
    date_evaluation = fields.Date(string='Evaluation Date', default=fields.Date.today, required=True)


    # Link to intervention
    intervention_id = fields.Many2one('fiche.intervention', string='Intervention',
                                      domain="[('installation_id', '=', installation_id)]", readonly="True")
    technicien_id = fields.Many2one(related='intervention_id.technicien_id', string='Technician', readonly=True,
                                    store=True)

    # Technical evaluation fields for installation
    performance_ratio = fields.Float(string='Performance Ratio (%)',
                                     help='Actual output compared to theoretical output')
    energy_produced = fields.Float(string='Energy Produced (kWh)')
    system_efficiency = fields.Float(string='System Efficiency (%)')

    # Maintenance evaluation for installation
    panel_condition = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('average', 'Average'),
        ('poor', 'Poor')
    ], string='Panel Condition', tracking=True)

    inverter_condition = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('average', 'Average'),
        ('poor', 'Poor')
    ], string='Inverter Condition', tracking=True)

    # Issues found
    issues_found = fields.Text(string='Issues Found')

    # Recommendations
    recommendations = fields.Text(string='Recommendations')

    # Technician evaluation fields
    technician_rating = fields.Selection([
        ('5', 'Excellent (5)'),
        ('4', 'Good (4)'),
        ('3', 'Average (3)'),
        ('2', 'Below Average (2)'),
        ('1', 'Poor (1)')
    ], string='Technician Rating', tracking=True)

    technician_knowledge = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('average', 'Average'),
        ('poor', 'Poor')
    ], string='Technical Knowledge', tracking=True)

    technician_professionalism = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('average', 'Average'),
        ('poor', 'Poor')
    ], string='Professionalism', tracking=True)

    technician_communication = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('average', 'Average'),
        ('poor', 'Poor')
    ], string='Communication Skills', tracking=True)

    technician_feedback = fields.Text(string='Feedback on Technician',
                                      help='Additional comments about technician performance')

    # State for workflow
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('done', 'Completed'),
        ('canceled', 'Canceled')
    ], string='Status', default='draft', tracking=True)

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('pv.evaluation.sequence') or 'New'
        return super(Evaluation, self).create(vals)

    @api.onchange('client_id')
    def _onchange_client_id(self):
        """When client changes, reset installation and update domain"""
        self.installation_id = False
        return {'domain': {'installation_id': [('client', '=', self.client_id.id)]}}

    @api.onchange('installation_id')
    def _onchange_installation_id(self):
        """Clear intervention when installation changes"""
        self.intervention_id = False
        return {'domain': {'intervention_id': [('installation_id', '=', self.installation_id.id)]}}

    # Action methods for state changes
    def action_draft(self):
        self.write({'state': 'draft'})

    def action_in_progress(self):
        self.write({'state': 'in_progress'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'canceled'})

    # Navigation methods
    def action_view_installation(self):
        self.ensure_one()
        return {
            'name': 'Installation',
            'view_mode': 'form',
            'res_model': 'pv.installation',
            'res_id': self.installation_id.id,
            'type': 'ir.actions.act_window',
        }

    def action_view_intervention(self):
        self.ensure_one()
        if not self.intervention_id:
            return
        return {
            'name': 'Intervention',
            'view_mode': 'form',
            'res_model': 'fiche.intervention',
            'res_id': self.intervention_id.id,
            'type': 'ir.actions.act_window',
        }