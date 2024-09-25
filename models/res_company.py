from email.policy import default
from odoo import api, fields, models
import pytz
from datetime import datetime
import logging
_logger = logging.getLogger(__name__)



class Company(models.Model):
    _inherit = 'res.company'

    is_gln          = fields.Char(string='GLN')
    is_regroupe_cde = fields.Selection(string='Regrouper les commandes', selection=[('Oui', 'Oui'), ('Non', 'Non')], default="Oui", help="Regrouper les commandes des clients sur les commandes fournisseur")

    is_date_bascule_tarif = fields.Date(string='Date bascule tarif client')

    is_coef_cdf_quai      = fields.Float(string='Taux de marge Cdf quai (%)'  , digits=(14,2))
    is_coef_cdf_franco    = fields.Float(string='Taux de marge Cdf franco (%)', digits=(14,2))
    is_coef_lf            = fields.Float(string='Taux de marge LF (%)'        , digits=(14,2))
    is_coef_lf_coll       = fields.Float(string='Taux de marge LF coll. (%)'  , digits=(14,2))
    is_coef_lf_franco     = fields.Float(string='Taux de marge LF franco (%)' , digits=(14,2))
    is_coef_ft            = fields.Float(string='Taux de marge FT (%)'        , digits=(14,2))

    is_port_cdf_quai      = fields.Float(string='Frais de port Cdf quai (€)'  , digits=(14,2))
    is_port_cdf_franco    = fields.Float(string='Frais de port Cdf franco (€)', digits=(14,2))
    is_port_lf            = fields.Float(string='Frais de port LF (€)'        , digits=(14,2))
    is_port_lf_coll       = fields.Float(string='Frais de port LF coll. (€)'  , digits=(14,2))
    is_port_lf_franco     = fields.Float(string='Frais de port LF franco (€)' , digits=(14,2))
    is_port_ft            = fields.Float(string='Frais de port FT (€)'        , digits=(14,2))


    def actualiser_tarif_futur_action(self):
        for obj in self:
            _logger.info("actualiser_tarif_futur_action : Début")
            self.env['product.template'].search([])._compute_tarifs(update_prix_actuel=False)
            #self.send_mail('actualiser_tarif_futur_action')
            _logger.info("actualiser_tarif_futur_action : Fin")


    # def actualiser_tarif_action(self):
    #     for obj in self:
    #         self.env['product.template'].search([])._compute_tarifs(update_prix_actuel=True)
    #         self.send_mail('actualiser_tarif_action')



    def actualiser_tarif_ft_action(self):
        for obj in self:
            self.env['product.template'].search([])._compute_tarifs(update_prix_actuel=True, pricelist='ft')
            #self.send_mail('actualiser_tarif_action')


    def actualiser_tarif_lf_franco_action(self):
        for obj in self:
            self.env['product.template'].search([])._compute_tarifs(update_prix_actuel=True, pricelist='lf_franco')
            #self.send_mail('actualiser_tarif_action')


    def appliquer_nouveaux_tarifs_action(self):
        self.env['product.template'].appliquer_nouveaux_tarifs_action()
        #self.send_mail('appliquer_nouveaux_tarifs_action')


    def send_mail(self,action): 
        tz = pytz.timezone('Europe/Paris')
        now = datetime.now(tz).strftime("%d/%m/%Y à %H:%M:%S")
        subject = "Action %s terminée le %s"%(action,now)
        body="""
            <p>Bonjour,</p> 
            <p>Traitement terminé</p> 
        """
        ctx = dict(
            default_model="res.company",
            default_res_id=self.id,
            default_composition_mode='comment',
            custom_layout='mail.mail_notification_light', #Permet de définir la mise en page du mail
        )
        infosaone_id=3128
        vals={
            "model"         : "res.company",
            "subject"       : subject,
            "body"          : body,
            "partner_ids"   : [self.env.user.partner_id.id,infosaone_id],
        }
        wizard = self.env['mail.compose.message'].with_context(ctx).create(vals)
        wizard.send_mail()
        return True

