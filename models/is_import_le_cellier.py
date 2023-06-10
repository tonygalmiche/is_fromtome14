# -*- coding: utf-8 -*-
from itertools import product
from odoo import api, fields, models, _
import codecs
import unicodedata
import base64
import openpyxl
import pytz
from datetime import datetime



def xls2float(val):
    try:
        res = float(val or 0)
    except ValueError:
        res = 0
    return res


class IsImportLeCellier(models.Model):
    _name = 'is.import.le.cellier'
    _description = "Importation de fichiers Excel pour Le Cellier"


    name     = fields.Char("Description", required=True)
    file_ids = fields.Many2many('ir.attachment', 'is_import_le_cellier_attachment_rel', 'doc_id', 'file_id', 'Fichiers')



    def importation_excel_action(self):
        for obj in self:
            for attachment in obj.file_ids:
                xlsxfile=base64.b64decode(attachment.datas)

                path = '/tmp/is_import_le_cellier-'+str(obj.id)+'.xlsx'
                f = open(path,'wb')
                f.write(xlsxfile)
                f.close()

                #** Test si fichier est bien du xlsx **************************
                try:
                    wb    = openpyxl.load_workbook(filename = path, data_only=True)
                    print(wb, wb.sheetnames) #['base 2022', 'HT 2022', 'FRANCO 2022']
                except:
                    raise Warning("Le fichier "+attachment.name+u" n'est pas un fichier xlsx")
                #**************************************************************


            # #** Création des listes de prix ***********************************
            # name = "Liste Prix CDF QUAI"
            # pricelist_quai = False
            # pricelists = self.env['product.pricelist'].search([("name","=",name)])
            # if len(pricelists):
            #     pricelist_quai = pricelists[0]
            #     pricelist_quai.item_ids.unlink()
            # else:
            #     vals={
            #         "name": name,
            #     }
            #     pricelist_quai=self.env['product.pricelist'].create(vals)
            # name = "Liste Prix CDF FRANCO"
            # pricelist_franco = False
            # pricelists = self.env['product.pricelist'].search([("name","=",name)])
            # if len(pricelists):
            #     pricelist_franco = pricelists[0]
            #     pricelist_franco.item_ids.unlink()
            # else:
            #     vals={
            #         "name": name,
            #     }
            #     pricelist_franco=self.env['product.pricelist'].create(vals)
            # #******************************************************************


            ws = wb['Sheet1']
            cells = list(ws)
            taxe_achat_id = self.env['ir.model.data'].xmlid_to_res_id('l10n_fr.1_tva_acq_reduite') # TVA déductible (achat) 5,5%
            taxe_vente_id = self.env['ir.model.data'].xmlid_to_res_id('l10n_fr.1_tva_reduite')     # TVA collectée (vente) 5,5%
            uom_id   = self.env['ir.model.data'].xmlid_to_res_id('uom.product_uom_kgm') # Kg
            lig=0
            ct=1
            for row in ws.rows:
                fournisseur                = cells[lig][0].value
                code_comptable_fournisseur = cells[lig][3].value
                code_fournisseur           = cells[lig][5].value
                ref_fournisseur            = cells[lig][7].value
                designation_fournisseur    = cells[lig][8].value
                ref_le_cellier             = cells[lig][9].value
                ref_fromtome               = cells[lig][10].value
                designation_interne        = cells[lig][11].value
                code_ean                   = cells[lig][12].value
                nouvelle_reference         = cells[lig][13].value
                lait                       = cells[lig][14].value
                traitement_thermique       = cells[lig][15].value
                colisage                   = xls2float(cells[lig][17].value)
                poids_colis                = xls2float(cells[lig][18].value)
                unite                      = cells[lig][19].value
                prix_brut                  = xls2float(cells[lig][21].value)
                remise1                    = xls2float(cells[lig][22].value)
                remise2                    = xls2float(cells[lig][23].value)
                remise3                    = xls2float(cells[lig][24].value)
                remise4                    = xls2float(cells[lig][25].value)
                remise5                    = xls2float(cells[lig][26].value)
                prix_quai                  = xls2float(cells[lig][30].value)
                prix_franco                = xls2float(cells[lig][31].value)


                #** Recherche du fournisseur **********************************
                partner=False
                if fournisseur and designation_interne and nouvelle_reference:
                    if fournisseur and code_comptable_fournisseur:
                        partners = self.env['res.partner'].search([("property_account_payable_id.code","=",code_comptable_fournisseur)])
                        if len(partners)>0:
                            partner = partners[0]
                        else:
                            partners = self.env['res.partner'].search([("name","=",fournisseur)])
                            if len(partners)>0:
                                partner = partners[0]
                    # if not partner and fournisseur:
                    #     vals={
                    #         "name": fournisseur,
                    #     }
                    #     partner = self.env['res.partner'].create(vals)
                    #     print("Création", fournisseur, code_comptable_fournisseur)
                # if partner and code_fournisseur and not partner.is_code_interne:
                #         vals={
                #             "is_code_interne" : code_fournisseur,
                #         }
                #         partner.write(vals)
                #**************************************************************

                #** Recherche article *****************************************
                product=False
                if partner and nouvelle_reference:
                    if nouvelle_reference:
                        products = self.env['product.template'].search([("default_code","=",nouvelle_reference)])
                        if not len(products) and ref_fromtome:
                            products = self.env['product.template'].search([("default_code","=",ref_fromtome)])
                        if not len(products) and code_ean:
                            products = self.env['product.template'].search([("barcode","=",code_ean)])
                    if len(products):
                        product = products[0]
                    # else:
                    #     vals={
                    #         "name"        : designation_interne,
                    #         "default_code": nouvelle_reference,
                    #     }
                    #     product = self.env['product.template'].create(vals)
                    #     print("Création", designation_interne)
                #**************************************************************


                #** Recherche du lait *****************************************
                lines = self.env['milk.type'].search([("name","=",lait)])
                milk_type_ids=False
                if len(lines):
                    milk_type_ids=[lines[0].id]
                #**************************************************************


                #** Création / Modification article ***************************
                if product:
                    print(lig,ct,products,nouvelle_reference,designation_interne)
                    tz = pytz.timezone('Europe/Paris')
                    now = datetime.now(tz).strftime("%d/%m/%Y à %H:%M:%S")
                    note = "Importé le %s"%(now)
                    vals={
                        "is_note_importation": note,
                        "default_code"       : nouvelle_reference,
                        "name"               : designation_interne,


                        #"taxes_id"           : [(6, 0, [taxe_vente_id])],
                        #"supplier_taxes_id"  : [(6, 0, [taxe_achat_id])],
                        #"type"               : "product",
                    }
                    # if unite=="Kg":
                    #     vals["uom_id"]    = uom_id
                    #     vals["uom_po_id"] = uom_id
                    # if colisage>0:
                    #     vals["is_nb_pieces_par_colis"] = colisage
                    # if poids_colis>0:
                    #     vals["is_poids_net_colis"] = poids_colis
                    # if milk_type_ids:
                    #     vals["milk_type_ids"] = [(6, 0, milk_type_ids)]
                    # traitements={
                    #     "Cru":"laitcru",
                    #     "Pasteurisé":"laitpasteurisé",
                    #     "Thermisé":"laitthermise",
                    # }
                    # if traitement_thermique in traitements:
                    #     vals["traitement_thermique"] = traitements[traitement_thermique]



                    product.write(vals)
                    ct+=1
                #**************************************************************

                # #** Tarif fournisseur *****************************************
                # if partner and product and prix_brut>0:
                #     product.seller_ids.unlink()
                #     vals={
                #         "product_tmpl_id": product.id,
                #         "name"           : partner.id,
                #         "product_code"   : ref_fournisseur,
                #         "prix_brut"      : prix_brut,
                #         "min_qty"        : 0,
                #         "date_start"     : "2023-01-01",
                #         "date_end"       : "2033-01-01",
                #     }
                #     supplierinfo = self.env['product.supplierinfo'].create(vals)
                #     if remise1>0:
                #         vals={
                #             "supplier_info_id": supplierinfo.id,
                #             "name"            : remise1*100,
                #         }
                #         self.env['product.supplierdiscount'].create(vals)
                #     if remise2>0:
                #         vals={
                #             "supplier_info_id": supplierinfo.id,
                #             "name"            : remise2*100,
                #         }
                #         self.env['product.supplierdiscount'].create(vals)
                #     if remise3>0:
                #         vals={
                #             "supplier_info_id": supplierinfo.id,
                #             "name"            : remise3*100,
                #         }
                #         self.env['product.supplierdiscount'].create(vals)
                #     if remise4>0:
                #         vals={
                #             "supplier_info_id": supplierinfo.id,
                #             "name"            : remise4*100,
                #         }
                #         self.env['product.supplierdiscount'].create(vals)
                #     if remise5>0:
                #         vals={
                #             "supplier_info_id": supplierinfo.id,
                #             "name"            : remise5*100,
                #         }
                #         self.env['product.supplierdiscount'].create(vals)
                # #**************************************************************


                # #** Liste de prix client **************************************
                # if pricelist_quai and product and prix_quai>0:
                #     vals={
                #         "pricelist_id"   : pricelist_quai.id,
                #         "applied_on"     : "1_product",
                #         "product_tmpl_id": product.id,
                #         "fixed_price"    : prix_quai,
                #     }
                #     self.env['product.pricelist.item'].create(vals)
                # if pricelist_franco and product and prix_franco>0:
                #     vals={
                #         "pricelist_id"   : pricelist_franco.id,
                #         "applied_on"     : "1_product",
                #         "product_tmpl_id": product.id,
                #         "fixed_price"    : prix_franco,
                #     }
                #     self.env['product.pricelist.item'].create(vals)
                # #**************************************************************


                lig+=1
