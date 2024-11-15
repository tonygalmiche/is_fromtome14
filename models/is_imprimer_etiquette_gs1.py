# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import codecs
import unicodedata
import base64
from datetime import datetime
from subprocess import check_output, STDOUT, CalledProcessError

class IsImprimanteEtiquette(models.Model):
    _name = 'is.imprimante.etiquette'
    _description = "Imprimante étiquettes"
    _order='name'

    name      = fields.Char("Nom de l'imprimante", required=True)
    name_cups = fields.Char("Nom CUPS", required=True)
    default   = fields.Boolean("Imprimante par défaut", default=False)
    dimension = fields.Selection([
            ('101x76', '101.6 x 76.2'),
            ('102x38', '102 x 38'),
        ], 'Dimensions étiquette', default='101x76', required=True)


class IsImprimerEtiquetteGS1(models.Model):
    _name = 'is.imprimer.etiquette.gs1'
    _description = "Imprimer des étiquettes GS1"
    _order='id desc'
    _rec_name = 'id'

    code_gs1   = fields.Text("Code GS1")
    code_ean   = fields.Char("Code EAN (01)")
    product_id = fields.Many2one('product.product', 'Article', required=True)
    type_tracabilite = fields.Selection(string='Traçabilité', related="product_id.is_type_tracabilite")
    lot        = fields.Char("Lot (10)", required=True)
    dlc        = fields.Date("DLC (17)")
    dluo       = fields.Date("DDM (15)")
    nb_pieces  = fields.Integer("Nb pièces (37)", required=True, default=1)
    poids      = fields.Float("Poids (31xx)"    , required=True, digits='Stock Weight')
    qt_imprime = fields.Integer("Quantité à Imprimer", required=True, default=1)
    imprimante_id = fields.Many2one('is.imprimante.etiquette', 'Imprimante étiquettes',default=lambda self: self.get_imprimante())
    alerte = fields.Text("Message")


    @api.model
    def create(self, vals):
        res = super(IsImprimerEtiquetteGS1, self).create(vals)
        res.imprimer_etiquette_action()
        return res


    def write(self, vals):
        res = super(IsImprimerEtiquetteGS1, self).write(vals)
        if "alerte" not in vals:
            for obj in self:
                obj.imprimer_etiquette_action()
        return res


    def get_imprimante(self):
        imprimante_id=self.env.user.is_imprimante_id.id
        if not imprimante_id:
            imprimantes = self.env['is.imprimante.etiquette'].search([('default', '=', True)],limit=1)
            for imprimante in imprimantes:
                imprimante_id = imprimante.id
        return imprimante_id
    

    def str2date(self,txt):
        try:
            dt = datetime.strptime(txt, "%y%m%d").strftime("%Y-%m-%d")
        except ValueError:
            dt = False
        return dt




    def get_ZPL(self):
        for obj in self:
            ZPL=''
            code_ean = self.code_ean or ''
            lot      = obj.lot or ''
           
            gs1 = "(01)"+code_ean
            if obj.dluo:
                gs1+=" (15)"+obj.dluo.strftime("%y%m%d")
            if obj.dlc:
                gs1+=" (17)"+obj.dlc.strftime("%y%m%d")
            gs1+=" (3103)"+("000000"+str(int(obj.poids*1000)))[-6:]
            gs1+=" (10)"+lot
            if obj.nb_pieces>1:
                gs1+=" (37)"+("00"+str(obj.nb_pieces))[-2:]

            #** Petite étiquette **********************************************
            if obj.imprimante_id.dimension=='102x38':

                code_designation="%s - %s"%(obj.product_id.default_code,obj.product_id.name) #[0:50]
                ligne1 = code_designation[0:55]
                ligne2 = code_designation[55:110]
                lot="LOT : %s"%lot
                if obj.type_tracabilite=='dlc':
                    dlc=''
                    if obj.dlc:
                        dlc=obj.dlc.strftime('%d/%m/%Y')
                    dlc_ddm="DLC : %s"%dlc
                else:
                    ddm=''
                    if obj.dluo:
                          ddm=obj.dluo.strftime('%d/%m/%Y')
                    dlc_ddm="DDM : %s"%ddm

                pcb="PCB : %s"%obj.product_id.is_nb_pieces_par_colis
                poids="POIDS NET : %.3fkg"%obj.poids
                ZPL="""
^XA
^CI28
^BY3


^CF0,44                       ^FX CF0 = Choix de la foncte (font 0) et taille de 44pt
^FO50,50^FD%s^FS              ^FX Position X,Y et texte ligne1
^FO50,100^FD%s^FS             ^FX Position X,Y et texte ligne2

^FO50,170^FD%s^FS             ^FX Position X,Y et texte lot
^FO50,220^FD%s^FS             ^FX Position X,Y et texte dlc/ddm

^FO800,170^FD%s^FS             ^FX Position X,Y et texte pcb
^FO800,220^FD%s^FS             ^FX Position X,Y et texte pouds

^FO50,280                     ^FX Position X,Y du code barre
^BCN,130,Y,N,,D               ^FX Code barre
^FD%s^FS

^XZ
            """ % (
                ligne1,
                ligne2,
                lot,
                dlc_ddm,

                pcb,
                poids,


                gs1
            )



            #** Grande étiquette **********************************************
            if obj.imprimante_id.dimension=='101x76':
                ZPL="""
^XA
^CI28
^BY3
^FO50,50^BCN,150,Y,N,,D
^FD%s^FS
^CF0,50                                     ^FX CF0 = Choix de la foncte (font 0) et taille de 40pt
^FO50,330^FDArticle : %s^FS                 ^FX Position et texte
^CF0,40                                     ^FX CF0 = Choix de la fonte (font 0) et taille de 30pt
^FO50,380^FD%s^FS                           ^FX Position et texte
^FO50,430^FDCode EAN (01) : %s^FS           ^FX Position et texte
^FO50,480^FDLot (10) : %s^FS                ^FX Position et texte
^FO50,580^FDDDM (15) : %s^FS                ^FX Position et texte
^FO50,530^FDDLC (17) : %s^FS                ^FX Position et texte
^FO50,630^FDPoids (3103) : %s^FS            ^FX Position et texte
^FO50,680^FDNb pièces (37) : %s^FS
^XZ
            """ % (
                gs1,
                obj.product_id.default_code,
                obj.product_id.name,
                code_ean,
                lot,
                obj.dluo or '',
                obj.dlc or '',
                round(obj.poids,4),
                obj.nb_pieces
            )

            return ZPL



    @api.onchange('code_gs1','product_id')
    def code_gs1_change(self):
        self.alerte=False

        if self.product_id and not self.lot:
            self.lot=(self.product_id.default_code or '')+datetime.now().strftime("%j%y")

        if self.product_id:
            if self.product_id.barcode:
                code_ean =  ((self.product_id.barcode or '')+"00000000000000")[:14]
            else:
                code_ean =  ((self.product_id.default_code or '')+"00000000000000")[:14]
                alerte="Création d'un code EAN, car l'article sélectionné n'a pas de code actuellement"
                self.alerte=alerte
            self.code_ean = code_ean

    def imprimer_etiquette_action(self):
        for obj in self:
            obj.alerte=False


#             code_ean = self.code_ean or ''
#             lot      = obj.lot or ''
           
#             gs1 = "(01)"+code_ean
#             if obj.dluo:
#                 gs1+=" (15)"+obj.dluo.strftime("%y%m%d")
#             if obj.dlc:
#                 gs1+=" (17)"+obj.dlc.strftime("%y%m%d")
#             gs1+=" (3103)"+("000000"+str(int(obj.poids*1000)))[-6:]
#             gs1+=" (10)"+lot
#             if obj.nb_pieces>1:
#                 gs1+=" (37)"+("00"+str(obj.nb_pieces))[-2:]



#             ZPL="""
# ^XA
# ^CI28
# ^BY3
# ^FO50,50^BCN,150,Y,N,,D
# ^FD%s^FS
# ^CF0,40                                     ^FX CF0 = Choix de la foncte (font 0) et taille de 40pt
# ^FO50,330^FDArticle : %s^FS                 ^FX Position et texte
# ^CF0,40                                     ^FX CF0 = Choix de la fonte (font 0) et taille de 30pt
# ^FO50,380^FD%s^FS                           ^FX Position et texte
# ^FO50,430^FDCode EAN (01) : %s^FS           ^FX Position et texte
# ^FO50,480^FDLot (10) : %s^FS                ^FX Position et texte
# ^FO50,580^FDDDM (15) : %s^FS                ^FX Position et texte
# ^FO50,530^FDDLC (17) : %s^FS                ^FX Position et texte
# ^FO50,630^FDPoids (3103) : %s^FS            ^FX Position et texte
# ^FO50,680^FDNb pièces (37) : %s^FS
# ^XZ
#             """ % (
#                 gs1,
#                 obj.product_id.default_code,
#                 obj.product_id.name,
#                 code_ean,
#                 lot,
#                 obj.dluo or '',
#                 obj.dlc or '',
#                 round(obj.poids,4),
#                 obj.nb_pieces
#             )


            ZPL = obj.get_ZPL()
            imprimante = obj.imprimante_id.name_cups or 'GX430T'
            name='etiquette-gs1-%s-zpl'%(imprimante)
            dest = '/tmp/'+name
            f = codecs.open(dest,'wb',encoding='utf-8')
            f.write(ZPL)
            f.close()
            cmd = "lpr -P %s %s "%(imprimante,dest)
            for x in range(0, obj.qt_imprime):
                try:
                    output = check_output(cmd, shell=True, stderr=STDOUT)
                except CalledProcessError as exc:
                    msg="%s \n%s"%(cmd,exc.output.decode("utf-8"))
                    alertes=[]
                    if obj.alerte:
                        alertes.append(obj.alerte)
                    alertes.append(msg)
                    obj.alerte="\n".join(alertes)


    def dupliquer_autre_poids_action(self):
        for obj in self:
            context = obj._context.copy()
            context['default_product_id'] = obj.product_id.id
            context['default_lot']        = obj.lot
            context['default_dlc']        = obj.dlc
            context['default_dluo']       = obj.dluo
            context['default_imprimante_id'] = obj.imprimante_id.id
            action = {
                'name': "Dupliquer",
                'view_mode': 'form',
                'res_model': 'is.imprimer.etiquette.gs1',
                'type': 'ir.actions.act_window',
                'context': context,
            }
            return action
