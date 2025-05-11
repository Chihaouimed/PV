from odoo import models, fields, api
from odoo.exceptions import ValidationError


class PVInstallation(models.Model):
    _name = 'pv.installation'
    _description = 'Solar PV Installation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    module_ids = fields.Many2many('pv.module', string='Modules PV')
    inverters_ids = fields.Many2many('pv.inverter', string='Onduleur PV')
    evaluation_ids = fields.One2many('pv.evaluation', 'installation_id', string='Evaluations')

    # Fields
    active = fields.Boolean(string='Active', default=True)
    name = fields.Char(string='Nom Instalation',required=True)
    code = fields.Char(string='Code', readonly=True, copy=False, default=lambda self: self.env['ir.sequence'].next_by_code('pv.installation.sequence') or 'Nouveau')
    client = fields.Many2one('res.partner', string='Client')
    cli = fields.Char(related='client.name', string='CLient', readonly=True)
    date_mise_en_service = fields.Date(string='Date d\'installation')
    address_id = fields.Char(string='Adresse')
    type_installation = fields.Selection([
        ('bt_residentiel', 'BT - Résidentiel'),
        ('bt_commercial', 'BT - Commercial'),
        ('mt_industriel', 'MT - Industriel')
    ], string="Type d'Installation")
    district_steg_id = fields.Many2one('configuration.district.steg', string='District STEG')
    reference_steg = fields.Integer(string='Reference STEG')
    type_compteur = fields.Selection([
        ('monophase', 'Monophasé'),
        ('triphase', 'Triphasé')
    ], string='Type de Compteur')

    calibre_disjoncteur_existant_id = fields.Many2one('configuration.district.steg',
                                                      string='Calibre Disjoncteur Existant (A)')
    calibre_disjoncteur_steg_id = fields.Many2one('configuration.district.steg', string='Calibre Disjoncteur STEG (A)')
    puissance_souscrite = fields.Float(string='Puissance Souscrite')
    consommation_annuelle = fields.Integer(string='Consommation Annuelle')
    # State Field
    state = fields.Selection(
        selection=[
            ('draft', 'Brouillon'),
            ('in_progress', 'En cours'),
            ('in_stop', 'Terminée'),
        ],
        string='État',
        default='draft',
        tracking=True
    )

    @api.model
    def create(self, vals):
        if vals.get('code', 'Nouveau') == 'Nouveau':
            vals['code'] = self.env['ir.sequence'].next_by_code('pv.installation.sequence') or 'Nouveau'
        return super(PVInstallation, self).create(vals)

    # State Change Methods
    def action_draft(self):
        self.write({'state': 'draft'})

    def action_in_progress(self):
        self.write({'state': 'in_progress'})

    def action_in_stop(self):
        self.write({'state': 'in_stop'})

