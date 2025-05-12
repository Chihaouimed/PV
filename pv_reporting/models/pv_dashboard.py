from odoo import models, fields, api
from datetime import datetime, timedelta
import json


class PVDashboard(models.Model):
    _name = 'pv.dashboard'
    _description = 'Tableau de bord PV'

    name = fields.Char(string='Nom', required=True)
    date_from = fields.Date(string='Date de début', default=lambda self: fields.Date.today() - timedelta(days=30))
    date_to = fields.Date(string='Date de fin', default=lambda self: fields.Date.today())

    # KPIs
    nb_installations = fields.Integer(string='Nombre d\'installations', compute='_compute_kpis')
    nb_installations_actives = fields.Integer(string='Installations actives', compute='_compute_kpis')
    nb_reclamations = fields.Integer(string='Nombre de réclamations', compute='_compute_kpis')
    nb_interventions = fields.Integer(string='Nombre d\'interventions', compute='_compute_kpis')
    taux_resolution = fields.Float(string='Taux de résolution (%)', compute='_compute_kpis')
    delai_moyen_intervention = fields.Float(string='Délai moyen d\'intervention (h)', compute='_compute_kpis')
    montant_total_facture = fields.Float(string='Montant total facturé', compute='_compute_kpis')
    montant_total_paye = fields.Float(string='Montant total payé', compute='_compute_kpis')
    taux_paiement = fields.Float(string='Taux de paiement (%)', compute='_compute_kpis')

    @api.depends('date_from', 'date_to')
    def _compute_kpis(self):
        for record in self:
            # Calcul des KPIs pour les installations
            installations = self.env['pv.installation'].search([])
            installations_actives = installations.filtered(lambda i: i.state in ['in_progress'])
            record.nb_installations = len(installations)
            record.nb_installations_actives = len(installations_actives)

            # Réclamations dans la période
            reclamations = self.env['reclamation'].search([
                ('date_heure', '>=', record.date_from),
                ('date_heure', '<=', record.date_to)
            ])
            record.nb_reclamations = len(reclamations)

            # Interventions dans la période
            interventions = self.env['fiche.intervention'].search([
                ('create_date', '>=', record.date_from),
                ('create_date', '<=', record.date_to)
            ])
            record.nb_interventions = len(interventions)

            # Taux de résolution (interventions fermées / total)
            interventions_fermees = interventions.filtered(lambda i: i.state == 'closed')
            record.taux_resolution = (len(interventions_fermees) / len(interventions) * 100) if interventions else 0

            # Délai moyen d'intervention
            delais = []
            for rec in reclamations:
                intervention = self.env['fiche.intervention'].search([('reclamation_id', '=', rec.id)], limit=1)
                if intervention:
                    delai = (intervention.create_date - rec.date_heure).total_seconds() / 3600  # en heures
                    delais.append(delai)
            record.delai_moyen_intervention = sum(delais) / len(delais) if delais else 0

            # Montants facturés et payés
            facturations = self.env['fiche.reponse'].search([
                ('date_cloture', '>=', record.date_from),
                ('date_cloture', '<=', record.date_to)
            ])

            record.montant_total_facture = sum(facturations.mapped('montant_a_payer'))
            montant_paye = sum(f.montant_a_payer for f in facturations if f.est_paye == 'oui')
            record.montant_total_paye = montant_paye
            record.taux_paiement = (
                        montant_paye / record.montant_total_facture * 100) if record.montant_total_facture else 0