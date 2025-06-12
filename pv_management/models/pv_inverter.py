from odoo import models, fields, api

class PVInverter(models.Model):
    _name = 'pv.inverter'
    _description = 'PV Inverter'

    # Inverter 1
    reference_onduleur_pv_id = fields.Char(string='Reference Onduleur PV', required=True, copy=False)
    marque_onduleur_pv_id = fields.Many2one('marque.onduleur', string='Marque Onduleur PV')
    puissance_onduleur_pv = fields.Char(string='Puissance Onduleur (KVA)')
    calibre_disjoncteur_onduleur_pv = fields.Many2one('configuration.district.steg' , string='Calibre Disjoncteur (A)')
    puissance_totale_ag = fields.Char(string='Puissance Totale AG (KVA)')


    # Add name_get method for better display in selection fields
    def name_get(self):
        result = []
        for inverter in self:
            marque = inverter.marque_onduleur_pv_id.name if inverter.marque_onduleur_pv_id else ''
            puissance = inverter.puissance_onduleur_pv or ''
            name = f"{inverter.reference_onduleur_pv_id} - {marque} {puissance}"
            result.append((inverter.id, name))
        return result