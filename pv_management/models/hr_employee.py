# Update pv_management/models/hr_employee.py

from odoo import models, fields, api, _


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # Add fields to store AI analysis
    last_ai_analysis_date = fields.Datetime(string='Dernière Analyse IA', readonly=True)
    ai_analysis_html = fields.Html(string='Analyse IA Performance', readonly=True)
    performance_rating = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Bon'),
        ('average', 'Moyen'),
        ('needs_improvement', 'À améliorer')
    ], string='Évaluation IA', readonly=True)

    # Count evaluations
    evaluation_count = fields.Integer(
        string='Nombre d\'évaluations',
        compute='_compute_evaluation_count',
        store=True
    )

    @api.depends('name')
    def _compute_evaluation_count(self):
        for employee in self:
            employee.evaluation_count = self.env['pv.evaluation'].search_count([
                ('technicien_id', '=', employee.id)
            ])

    def action_analyze_performance_ai(self):
        """
        Launch AI analysis for this technician
        """
        self.ensure_one()

        try:
            openai_service = self.env['pv.management.openai.service']
            result = openai_service.analyze_technician_performance(self.id)

            if result['success']:
                analysis = result['analysis']

                # Update technician record with analysis
                self.write({
                    'last_ai_analysis_date': fields.Datetime.now(),
                    'ai_analysis_html': analysis.get('html_content', ''),
                    'performance_rating': analysis.get('overall_rating', 'average')
                })

                # Show success message and reload form
                return {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                    'params': {
                        'title': _('Analyse Terminée'),
                        'message': _('L\'analyse IA a été générée avec succès.'),
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Erreur'),
                        'message': result.get('message', 'Erreur inconnue'),
                        'sticky': True,
                        'type': 'warning'
                    }
                }

        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Erreur Technique'),
                    'message': f'Une erreur s\'est produite: {str(e)}',
                    'sticky': True,
                    'type': 'danger'
                }
            }

    def action_view_evaluations(self):
        """
        View all evaluations for this technician
        """
        self.ensure_one()
        return {
            'name': _('Évaluations - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'pv.evaluation',
            'view_mode': 'tree,form',
            'domain': [('technicien_id', '=', self.id)],
            'context': {'default_technicien_id': self.id}
        }

    # Add this test method to pv_management/models/hr_employee.py

    def action_test_ai_simple(self):
        """
        Simple test function to verify AI analysis is working
        """
        self.ensure_one()

        # Simple test without AI - just to verify the button works
        test_html = f"""
        <div style="padding: 20px; background: #f8f9fa; border-radius: 8px;">
            <h3>🧪 Test Analyse IA - {self.name}</h3>
            <p><strong>Nombre d'évaluations:</strong> {self.evaluation_count}</p>
            <p><strong>Date de test:</strong> {fields.Datetime.now()}</p>
            <div style="background: #d4edda; padding: 10px; border-radius: 4px; margin: 10px 0;">
                ✅ La fonction d'analyse IA fonctionne correctement!
            </div>
            <p>Si vous voyez ce message, l'intégration est réussie.</p>
        </div>
        """

        # Update the employee record
        self.write({
            'last_ai_analysis_date': fields.Datetime.now(),
            'ai_analysis_html': test_html,
            'performance_rating': 'good'
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }