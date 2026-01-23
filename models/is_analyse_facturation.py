# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from datetime import datetime, timedelta, date
from odoo.addons.is_fromtome14.models.account_move import _TYPE_AVOIR

import logging
_logger = logging.getLogger(__name__)


_MOVE_TYPE={
    'out_invoice': 'Facture client',
    'out_refund' : 'Avoir client',
    'in_invoice' : 'Facture fournisseur',
    'in_refund'  : 'Avoir fournisseur',
    'rebut'      : 'Rebut',
}


class IsAnalyseFacturationUpdate(models.TransientModel):
    _name = 'is.analyse.facturation.update'
    _description = "Mise à jour analyse de facturation"

    date_debut = fields.Date('Date début', required=True, default=lambda self: fields.Datetime.now()-timedelta(30))
    date_fin   = fields.Date('Date fin'  , required=True, default=lambda self: fields.Datetime.now())


    def action_ok(self):
        self.update(self.date_debut,self.date_fin)


    def update(self, date_debut, date_fin):
        cr, user, context, su = self.env.args
        filtre=[
            ('invoice_date','>=',date_debut),
            ('invoice_date','<=',date_fin),
            ('bloquer','=', True),
        ]
        lines=self.env['is.analyse.facturation'].search(filtre)
        invoice_line_ids=scrap_ids=[]
        for line in lines:
            if line.invoice_line_id:
                invoice_line_ids.append(line.invoice_line_id.id)
            if line.scrap_id:
                scrap_ids.append(line.scrap_id.id)

        sql="""
            delete from is_analyse_facturation
            where invoice_date>=%s and invoice_date<=%s and bloquer='f'
        """
        cr.execute(sql,[date_debut, date_fin])
        filtre=[
            ('invoice_date','>=',date_debut),
            ('invoice_date','<=',date_fin),
            ('state','=','posted'),
        ]
        invoices = self.env['account.move'].search(filtre)
        nb=len(invoices)
        ct=0
        for invoice in invoices:
            ct+=1
            _logger.info("%s/%s : %s"%(ct,nb,invoice.name))
            for line in invoice.invoice_line_ids:
                if line.id not in invoice_line_ids:
                    if line.price_subtotal>0.0:
                        sens=1
                        if invoice.move_type in ["out_refund","in_invoice"]:
                            sens=-1

                        is_type_avoir = False
                        if invoice.move_type in('out_refund','in_refund'):
                            is_type_avoir = invoice.is_type_avoir


                        #** Recherche du dernier prix d'achat pour cet article ****
                        prix_achat=montant_achat=marge_brute=discount_fournisseur=0
                        ligne_facture_fournisseur_id = date_facture_fournisseur = False
                        fournisseur_id = False
                        if invoice.move_type in ('out_invoice', 'out_refund'):
                            if is_type_avoir!='avoir_prix':
                                sql="""
                                    SELECT  
                                        aml.price_unit,
                                        am.invoice_date,
                                        aml.id,
                                        am.partner_id,
                                        aml.discount
                                    FROM account_move_line aml inner join account_move am on aml.move_id=am.id
                                    WHERE 
                                        am.invoice_date<=%s and
                                        aml.product_id=%s and
                                        am.move_type='in_invoice'
                                    ORDER BY am.invoice_date desc
                                    limit 1
                                """
                                cr.execute(sql,[invoice.invoice_date, line.product_id.id])
                                for row in cr.fetchall():
                                    prix_achat                   = row[0]
                                    date_facture_fournisseur     = row[1]
                                    ligne_facture_fournisseur_id = row[2]
                                    fournisseur_id               = row[3]
                                    discount_fournisseur         = row[4] or 0
                                    montant_achat = prix_achat*line.quantity*sens
                            marge_brute = line.price_subtotal*sens-montant_achat
                        #**********************************************************

                        #** Calcul avec remise fournisseur *************************
                        montant_achat_avec_remise = montant_achat * (1 - discount_fournisseur / 100)
                        marge_brute_avec_remise = line.price_subtotal*sens - montant_achat_avec_remise
                        #**********************************************************

                        #** Poids en fonction du type d'avoir et du sens **********
                        poids_net = sens*line.is_poids_net or 0
                        if is_type_avoir=='avoir_prix':
                            poids_net=0
                        #**********************************************************





                        vals={
                            "invoice_id"     : invoice.id,
                            "invoice_line_id": line.id,
                            "invoice_date"  : invoice.invoice_date,
                            "partner_id"    : invoice.partner_id.id,
                            "user_id"       : invoice.partner_id.user_id.id,
                            "enseigne"      : invoice.is_enseigne_id.name.name,
                            "product_id"    : line.product_id.id,
                            "product_uom_id": line.product_uom_id.id,
                            "libelle"       : line.name,
                            "quantity"      : line.quantity,
                            "nb_colis"      : sens*(line.is_nb_colis or 0),
                            "poids_net"     : poids_net,
                            "price_unit"    : line.price_unit,
                            "discount"      : line.discount,
                            "price_subtotal": line.price_subtotal*sens,
                            "move_type"     : _MOVE_TYPE[invoice.move_type],
                            "is_type_avoir" : is_type_avoir,
                            "prix_achat"    : prix_achat,
                            "montant_achat" : montant_achat,
                            "marge_brute"   : marge_brute,
                            "montant_achat_avec_remise": montant_achat_avec_remise,
                            "marge_brute_avec_remise"  : marge_brute_avec_remise,
                            "ligne_facture_fournisseur_id": ligne_facture_fournisseur_id,
                            "date_facture_fournisseur"    : date_facture_fournisseur,
                            "fournisseur_id"              : fournisseur_id,
                            "discount_fournisseur"        : discount_fournisseur or 0,
                        }
                        self.env['is.analyse.facturation'].create(vals)

        filtre=[
            ('date_done','>=',date_debut),
            ('date_done','<',date_fin+timedelta(1)),
            ('state','=','done'),
        ]
        scraps = self.env['stock.scrap'].search(filtre)
        nb=len(scraps)
        ct=0
        for scrap in scraps:
            if scrap.id not in scrap_ids:
                ct+=1
                _logger.info("%s/%s : %s"%(ct,nb,scrap.name))

                price_unit = 0
                partner_id=enseigne_id=user_id=False
                enseigne = False
                for purchase in scrap.lot_id.purchase_order_ids:
                    partner_id  = purchase.partner_id.id
                    enseigne    = purchase.partner_id.is_enseigne_id.name.name
                    user_id     = purchase.partner_id.user_id.id
                    for line in purchase.order_line:
                        if line.product_id == scrap.product_id:
                            price_unit=line.price_unit
                price_subtotal = -price_unit * scrap.scrap_qty

                nb_colis = 0
                poids_net = 0
                if scrap.product_id.is_nb_pieces_par_colis>0:
                    nb_colis = scrap.scrap_qty / scrap.product_id.is_nb_pieces_par_colis
                    poids_net = nb_colis * scrap.product_id.is_poids_net_colis
                vals={
                    "scrap_id"      : scrap.id,
                    "invoice_date"  : scrap.date_done,
                    "partner_id"    : partner_id,
                    "user_id"       : user_id,
                    "enseigne"      : enseigne,
                    "product_id"    : scrap.product_id.id,
                    "product_uom_id": scrap.product_id.uom_id.id,
                    "libelle"       : scrap.name+" / "+(scrap.origin or ''),
                    "quantity"      : scrap.scrap_qty,
                    "nb_colis"      : nb_colis,
                    "poids_net"     : -poids_net,
                    "price_unit"    : price_unit,
                    "price_subtotal": price_subtotal,
                    "marge_brute"   : price_subtotal,
                    "montant_achat_avec_remise": 0,
                    "marge_brute_avec_remise"  : price_subtotal,
                    "move_type"     : "Rebut",
                    "fournisseur_id": partner_id,
                }
                self.env['is.analyse.facturation'].create(vals)

        res= {
            'name': 'Analyse facturation',
            'view_mode': 'tree,form,pivot,graph',
            'res_model': 'is.analyse.facturation',
            'type': 'ir.actions.act_window',
        }
        return res


class IsAnalyseFacturation(models.Model):
    _name = 'is.analyse.facturation'
    _description = "Analyse facturation"
    _order = 'invoice_date desc,move_type'


    invoice_date      = fields.Date("Date", help="Date facture, avoir ou rebut", required=True)
    invoice_id        = fields.Many2one('account.move', 'Facture')
    invoice_line_id   = fields.Many2one('account.move.line', 'Ligne de Facture', index=True)
    scrap_id          = fields.Many2one('stock.scrap', 'Rebut')
    partner_id        = fields.Many2one('res.partner', 'Partenaire')
    user_id           = fields.Many2one('res.users', 'Vendeur')
    enseigne          = fields.Char('Enseigne')
    product_id        = fields.Many2one('product.product', 'Article')
    product_uom_id    = fields.Many2one('uom.uom', 'Unité')
    libelle           = fields.Text('Libellé')
    quantity          = fields.Float("Quantité", digits='Product Unit of Measure')
    poids_net         = fields.Float(string='Poids net', digits=(14,3))
    nb_colis          = fields.Float(string='Nb colis' , digits=(14,1))
    price_unit        = fields.Float("Prix"    , digits='Product Price')
    discount          = fields.Float("Remise", digits='Discount')
    price_subtotal    = fields.Float("Montant HT")

    discount_fournisseur = fields.Float("Remise fournisseur", digits='Discount')

    prix_achat        = fields.Float("Prix d'achat" , digits='Product Price')
    montant_achat     = fields.Float("Montant achat sans remise")
    marge_brute       = fields.Float("Marge brute sans remise fournisseur")
    montant_achat_avec_remise = fields.Float("Montant achat avec remise")
    marge_brute_avec_remise   = fields.Float("Marge brute avec remise fournisseur")
    ligne_facture_fournisseur_id = fields.Many2one('account.move.line', 'Ligne facture fournisseur')
    date_facture_fournisseur     = fields.Date("Date facture fournisseur")
    fournisseur_id               = fields.Many2one('res.partner', 'Fournisseur')
    move_type = fields.Selection([
            ('Facture client'     , 'Facture client'),
            ('Avoir client'       , 'Avoir client'),
            ('Facture fournisseur', 'Facture fournisseur'),
            ('Avoir fournisseur'  , 'Avoir fournisseur'),
            ('Rebut'              , 'Rebut'),
        ], 'Type')
    is_type_avoir = fields.Selection(_TYPE_AVOIR, 'Type avoir')
    bloquer = fields.Boolean("Bloquer la mise à jour de cette fiche", help="A utiliser pour corriger une errreur dans Odoo", default=False, index=True)


    @api.model
    def analyse_facturation_ir_cron(self):
        date_fin = date.today()
        date_debut = date_fin - timedelta(30)
        self.env['is.analyse.facturation.update'].update(date_debut,date_fin)
        return True
    

    def update_fournisseur_action(self):
        for obj in self:
            obj.fournisseur_id = obj.ligne_facture_fournisseur_id.move_id.partner_id.id


    def update_discount_action(self):
        """Actualise les champs discount et discount_fournisseur à partir des lignes de factures"""
        cr = self.env.cr
        debut = datetime.now()
        
        _logger.info("Début de la mise à jour globale des champs discount et discount_fournisseur")
        
        # Mise à jour globale directe via SQL (sans limite de sélection)
        # Mise à jour discount client
        sql = """
            UPDATE is_analyse_facturation iaf
            SET discount = COALESCE(aml.discount, 0)
            FROM account_move_line aml
            WHERE iaf.invoice_line_id = aml.id
            AND iaf.invoice_line_id IS NOT NULL
        """
        
        cr.execute(sql)
        nb_lignes = cr.rowcount
        
        # Mettre à 0 les lignes sans invoice_line_id (rebuts, etc.)
        sql2 = """
            UPDATE is_analyse_facturation
            SET discount = 0
            WHERE invoice_line_id IS NULL
        """
        
        cr.execute(sql2)
        nb_lignes2 = cr.rowcount
        
        # Mise à jour discount_fournisseur
        sql3 = """
            UPDATE is_analyse_facturation iaf
            SET discount_fournisseur = COALESCE(aml.discount, 0)
            FROM account_move_line aml
            WHERE iaf.ligne_facture_fournisseur_id = aml.id
            AND iaf.ligne_facture_fournisseur_id IS NOT NULL
        """
        
        cr.execute(sql3)
        nb_lignes3 = cr.rowcount
        
        # Mettre à 0 les lignes sans ligne_facture_fournisseur_id
        sql4 = """
            UPDATE is_analyse_facturation
            SET discount_fournisseur = 0
            WHERE ligne_facture_fournisseur_id IS NULL
        """
        
        cr.execute(sql4)
        nb_lignes4 = cr.rowcount
        
        # Recalcul du montant_achat_avec_remise et marge_brute_avec_remise
        sql5 = """
            UPDATE is_analyse_facturation
            SET montant_achat_avec_remise = montant_achat * (1 - discount_fournisseur / 100),
                marge_brute_avec_remise = price_subtotal - (montant_achat * (1 - discount_fournisseur / 100))
            WHERE move_type != 'Rebut'
        """
        
        cr.execute(sql5)
        nb_lignes5 = cr.rowcount
        
        # Pour les rebuts, marge_brute_avec_remise = marge_brute
        sql6 = """
            UPDATE is_analyse_facturation
            SET montant_achat_avec_remise = 0,
                marge_brute_avec_remise = marge_brute
            WHERE move_type = 'Rebut'
        """
        
        cr.execute(sql6)
        nb_lignes6 = cr.rowcount
        cr.commit()
        
        duree = datetime.now() - debut
        _logger.info("Mise à jour terminée en %s: discount (%s avec facture + %s sans facture), discount_fournisseur (%s avec facture + %s sans facture), montants recalculés (%s factures + %s rebuts)", 
                     duree, nb_lignes, nb_lignes2, nb_lignes3, nb_lignes4, nb_lignes5, nb_lignes6)

