from odoo import models, fields, api, tools
from datetime import datetime, timedelta


class PVInstallationReport(models.Model):
    _name = 'pv.installation.report'
    _description = 'Reporting sur les Installations PV'
    _auto = False
    _order = 'date_mise_en_service desc'

    installation_id = fields.Many2one('pv.installation', string='Installation', readonly=True)
    name = fields.Char(string='Nom Installation', readonly=True)
    code = fields.Char(string='Code Installation', readonly=True)
    client_id = fields.Many2one('res.partner', string='Client', readonly=True)
    client_name = fields.Char(string='Nom Client', readonly=True)
    date_mise_en_service = fields.Date(string='Date Mise en Service', readonly=True)
    type_installation = fields.Selection([
        ('bt_residentiel', 'BT - Résidentiel'),
        ('bt_commercial', 'BT - Commercial'),
        ('mt_industriel', 'MT - Industriel')
    ], string="Type d'Installation", readonly=True)
    district_steg_id = fields.Many2one('configuration.district.steg', string='District STEG', readonly=True)
    puissance_souscrite = fields.Float(string='Puissance Souscrite', readonly=True)
    consommation_annuelle = fields.Integer(string='Consommation Annuelle', readonly=True)
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('in_progress', 'En cours'),
        ('in_stop', 'Terminée'),
    ], string='État', readonly=True)
    nb_modules = fields.Integer(string='Nombre de Modules', readonly=True)
    nb_onduleurs = fields.Integer(string='Nombre d\'Onduleurs', readonly=True)

    # Champs pour analyse temporelle
    year = fields.Char(string='Année', readonly=True)
    month = fields.Char(string='Mois', readonly=True)
    quarter = fields.Char(string='Trimestre', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    pi.id as id,
                    pi.id as installation_id,
                    pi.name as name,
                    pi.code as code,
                    pi.client as client_id,
                    rp.name as client_name,
                    pi.date_mise_en_service,
                    pi.type_installation,
                    pi.district_steg_id,
                    pi.puissance_souscrite,
                    pi.consommation_annuelle,
                    pi.state,
                    (SELECT COUNT(*) FROM pv_installation_pv_module_rel rel WHERE rel.pv_installation_id = pi.id) as nb_modules,
                    (SELECT COUNT(*) FROM pv_installation_pv_inverter_rel rel WHERE rel.pv_installation_id = pi.id) as nb_onduleurs,
                    TO_CHAR(pi.date_mise_en_service, 'YYYY') as year,
                    TO_CHAR(pi.date_mise_en_service, 'MM') as month,
                    CONCAT('Q', EXTRACT(QUARTER FROM pi.date_mise_en_service)) as quarter
                FROM
                    pv_installation pi
                LEFT JOIN
                    res_partner rp ON pi.client = rp.id
            )
        """ % self._table)


class PVReclamationReport(models.Model):
    _name = 'pv.reclamation.report'
    _description = 'Reporting sur les Réclamations'
    _auto = False
    _order = 'date_heure desc'

    reclamation_id = fields.Many2one('reclamation', string='Réclamation', readonly=True)
    name = fields.Char(string='Référence', readonly=True)
    date_heure = fields.Datetime(string='Date et Heure', readonly=True)
    client_id = fields.Many2one('res.partner', string='Client', readonly=True)
    installation_id = fields.Many2one('pv.installation', string='Installation', readonly=True)
    installation_name = fields.Char(string='Nom Installation', readonly=True)
    code_alarm_id = fields.Many2one('alarm.management', string='Code Alarme', readonly=True)
    code_alarm_name = fields.Char(string='Nom Alarme', readonly=True)
    priorite_urgence = fields.Selection([
        ('basse', 'Basse'),
        ('moyenne', 'Moyenne'),
        ('haute', 'Haute')
    ], string='Priorité d\'urgence', readonly=True)
    nb_interventions = fields.Integer(string='Nombre d\'Interventions', readonly=True)

    # Délai de traitement
    date_disponibilite = fields.Datetime(string='Date de Disponibilité', readonly=True)
    delai_intervention_heures = fields.Float(string='Délai d\'Intervention (Heures)', readonly=True)

    # Champs pour analyse temporelle
    year = fields.Char(string='Année', readonly=True)
    month = fields.Char(string='Mois', readonly=True)
    quarter = fields.Char(string='Trimestre', readonly=True)
    week = fields.Char(string='Semaine', readonly=True)
    day = fields.Char(string='Jour', readonly=True)
    hour = fields.Char(string='Heure', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    r.id as id,
                    r.id as reclamation_id,
                    r.name as name,
                    r.date_heure,
                    r.client_id,
                    r.nom_central_id as installation_id,
                    pi.name as installation_name,
                    r.code_alarm_id,
                    am.name as code_alarm_name,
                    r.priorite_urgence,
                    r.date_disponibilite,
                    (SELECT COUNT(*) FROM fiche_intervention fi WHERE fi.reclamation_id = r.id) as nb_interventions,
                    EXTRACT(EPOCH FROM (
                        COALESCE(
                            (SELECT MIN(f.create_date) FROM fiche_intervention f WHERE f.reclamation_id = r.id),
                            NOW()
                        ) - r.date_heure)) / 3600 as delai_intervention_heures,
                    TO_CHAR(r.date_heure, 'YYYY') as year,
                    TO_CHAR(r.date_heure, 'MM') as month,
                    CONCAT('Q', EXTRACT(QUARTER FROM r.date_heure)) as quarter,
                    TO_CHAR(r.date_heure, 'WW') as week,
                    TO_CHAR(r.date_heure, 'DD') as day,
                    TO_CHAR(r.date_heure, 'HH24') as hour
                FROM
                    reclamation r
                LEFT JOIN
                    pv_installation pi ON r.nom_central_id = pi.id
                LEFT JOIN
                    alarm_management am ON r.code_alarm_id = am.id
            )
        """ % self._table)


class PVInterventionReport(models.Model):
    _name = 'pv.intervention.report'
    _description = 'Reporting sur les Interventions'
    _auto = False
    _order = 'create_date desc'

    intervention_id = fields.Many2one('fiche.intervention', string='Intervention', readonly=True)
    name = fields.Char(string='Référence', readonly=True)
    create_date = fields.Datetime(string='Date de Création', readonly=True)
    type_intervention = fields.Selection([
        ('maintenance', 'Maintenance'),
        ('installation', 'Installation'),
        ('reparation', 'Réparation'),
        ('inspection', 'Inspection'),
        ('autre', 'Autre')
    ], string='Type d\'intervention', readonly=True)

    installation_id = fields.Many2one('pv.installation', string='Installation', readonly=True)
    installation_name = fields.Char(string='Nom Installation', readonly=True)
    client_id = fields.Many2one('res.partner', string='Client', readonly=True)
    client_name = fields.Char(string='Nom Client', readonly=True)
    technicien_id = fields.Many2one('hr.employee', string='Technicien', readonly=True)
    technicien_name = fields.Char(string='Nom Technicien', readonly=True)
    reclamation_id = fields.Many2one('reclamation', string='Réclamation', readonly=True)
    nombre_interventions = fields.Integer(string='Nombre d\'interventions', readonly=True, default=1)

    state = fields.Selection([
        ('draft', 'Ouvert'),
        ('in_progress', 'En cours'),
        ('closed', 'Fermé'),
    ], string='État', readonly=True)

    # Durée d'intervention
    duree_intervention_jours = fields.Float(string='Durée Intervention (Jours)', readonly=True)

    # Détails de facturation/paiement
    montant_total = fields.Float(string='Montant Total', readonly=True)
    montant_paye = fields.Float(string='Montant Payé', readonly=True)
    est_payee = fields.Boolean(string='Est Payée', readonly=True)

    # Évaluations
    note_technicien = fields.Selection([
        ('5', 'Excellent (5)'),
        ('4', 'Good (4)'),
        ('3', 'Average (3)'),
        ('2', 'Below Average (2)'),
        ('1', 'Poor (1)')
    ], string='Note Technicien', readonly=True)

    # Champs pour analyse temporelle
    year = fields.Char(string='Année', readonly=True)
    month = fields.Char(string='Mois', readonly=True)
    quarter = fields.Char(string='Trimestre', readonly=True)
    week = fields.Char(string='Semaine', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    fi.id as id,
                    fi.id as intervention_id,
                    fi.name as name,
                    fi.create_date,
                    fi.type_intervention,
                    fi.installation_id,
                    pi.name as installation_name,
                    pi.client as client_id,
                    rp.name as client_name,
                    fi.technicien_id,
                    he.name as technicien_name,
                    fi.reclamation_id,
                    fi.state,
                    EXTRACT(EPOCH FROM (
                        CASE WHEN fi.state = 'closed' THEN
                            (SELECT MAX(fr.date_cloture) FROM fiche_reponse fr WHERE fr.intervention_id = fi.id)
                        ELSE
                            NOW()
                        END - fi.create_date)) / 86400 as duree_intervention_jours,
                    (SELECT COALESCE(SUM(fr.montant_a_payer), 0) FROM fiche_reponse fr WHERE fr.intervention_id = fi.id) as montant_total,
                    (SELECT COALESCE(SUM(CASE WHEN fr.est_paye = 'oui' THEN fr.montant_a_payer ELSE 0 END), 0) 
                     FROM fiche_reponse fr WHERE fr.intervention_id = fi.id) as montant_paye,
                    CASE WHEN (
                        SELECT COUNT(*) FROM fiche_reponse fr 
                        WHERE fr.intervention_id = fi.id AND fr.est_paye = 'non'
                    ) = 0 AND (
                        SELECT COUNT(*) FROM fiche_reponse fr 
                        WHERE fr.intervention_id = fi.id
                    ) > 0 THEN true ELSE false END as est_payee,
                    (SELECT pe.technician_rating FROM pv_evaluation pe WHERE pe.intervention_id = fi.id LIMIT 1) as note_technicien,
                    TO_CHAR(fi.create_date, 'YYYY') as year,
                    TO_CHAR(fi.create_date, 'MM') as month,
                    CONCAT('Q', EXTRACT(QUARTER FROM fi.create_date)) as quarter,
                    TO_CHAR(fi.create_date, 'WW') as week,
                    1 as nombre_interventions
                FROM
                    fiche_intervention fi
                LEFT JOIN
                    pv_installation pi ON fi.installation_id = pi.id
                LEFT JOIN
                    res_partner rp ON pi.client = rp.id
                LEFT JOIN
                    hr_employee he ON fi.technicien_id = he.id
            )
        """ % self._table)