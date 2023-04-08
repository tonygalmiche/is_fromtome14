# -*- coding: utf-8 -*-
from itertools import product
from odoo import api, fields, models, _
import codecs
import unicodedata
import base64
import openpyxl


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
                if fournisseur and designation_interne and nouvelle_reference:

                    #** Recherche du fournisseur ******************************
                    if fournisseur:
                        partners = self.env['res.partner'].search([("name","ilike",fournisseur)])
                        for p in partners:
                            partner = p
                        if len(partners)==0:
                            vals={
                                "name": fournisseur,
                            }
                            partner=self.env['res.partner'].create(vals)
                            #print("CREATION ",partner)
                        else:
                            partner=partner[0]
                            vals={
                                "is_code_fromtome": code_comptable_fournisseur,
                                "is_code_interne" : code_fournisseur,
                            }
                            #partner.write(vals)
                            #print("MAJ ",partner)
                    #**********************************************************

                    #** Recherche article *************************************
                    # barecode=0
                    # try:
                    #     barecode = int(code_ean)
                    # except ValueError:
                    #     pass
                    if code_ean or ref_fromtome or nouvelle_reference:
                        products=False
                        if nouvelle_reference:
                            products = self.env['product.template'].search([("default_code","=",nouvelle_reference)])
                            if not len(products) and ref_fromtome:
                                products = self.env['product.template'].search([("default_code","=",ref_fromtome)])
                            if not len(products) and code_ean:
                                products = self.env['product.template'].search([("barcode","=",code_ean)])
                        if products:
                            print(ct,products,code_ean, ref_fromtome, nouvelle_reference)
                            ct+=1
                lig+=1

                #if ct>20:
                #    break



    # def create_pricelist(self, wb, worksheet_name, pricelist_name):
    #     for obj in self: 
    #         pricelists = self.env['product.pricelist'].search([("name","=",pricelist_name)])
    #         vals={
    #             "name": pricelist_name,
    #         }
    #         if len(pricelists)==0:
    #             pricelist=self.env['product.pricelist'].create(vals)
    #         else:
    #             pricelist = pricelists[0]
    #             pricelist.write(vals)
    #         pricelist.item_ids.unlink()
    #         ws = wb[worksheet_name]
    #         cells = list(ws)
    #         lig=ct=0
    #         for row in ws.rows:
    #             code        = cells[lig][1].value
    #             prix        = xls2float(cells[lig][8].value)
    #             if code and prix:
    #                 products = self.env['product.template'].search([("default_code","=",code)])
    #                 for product in products:
    #                     vals={
    #                         "pricelist_id"   : pricelist.id,
    #                         "applied_on"     : "1_product",
    #                         "product_tmpl_id": product.id,
    #                         "fixed_price"    : prix,
    #                     }
    #                     items=self.env['product.pricelist.item'].create(vals)
    #                     print(ct, lig, code, prix, items)
    #                     ct+=1
    #             lig+=1


    # def importation_excel_action(self):
    #     for obj in self:
    #         for attachment in obj.file_ids:
    #             xlsxfile=base64.b64decode(attachment.datas)

    #             path = '/tmp/is_import_le_cellier-'+str(obj.id)+'.xlsx'
    #             f = open(path,'wb')
    #             f.write(xlsxfile)
    #             f.close()

    #             #** Test si fichier est bien du xlsx **************************
    #             try:
    #                 wb    = openpyxl.load_workbook(filename = path, data_only=True)
    #                 print(wb.sheetnames) #['base 2022', 'HT 2022', 'FRANCO 2022']
    #             except:
    #                 raise Warning("Le fichier "+attachment.name+u" n'est pas un fichier xlsx")
    #             #**************************************************************


    #         ws = wb['base 2022']
    #         cells = list(ws)
    #         taxe_achat_id = self.env['ir.model.data'].xmlid_to_res_id('l10n_fr.1_tva_acq_reduite') # TVA déductible (achat) 5,5%
    #         taxe_vente_id = self.env['ir.model.data'].xmlid_to_res_id('l10n_fr.1_tva_reduite')     # TVA collectée (vente) 5,5%

    #         uom_id   = self.env['ir.model.data'].xmlid_to_res_id('uom.product_uom_kgm') # Kg

    #         lig=ct=0
    #         for row in ws.rows:
    #             fournisseur = cells[lig][0].value
    #             code        = cells[lig][1].value
    #             designation = cells[lig][2].value
    #             colisage    = xls2float(cells[lig][6].value)
    #             poids       = xls2float(cells[lig][7].value)
    #             prix        = xls2float(cells[lig][10].value)
    #             kg_piece    = cells[lig][16].value

    #             #** Recherche du fournisseur ******************************
    #             partner_id = False # Fournisseur = My Company
    #             if fournisseur:
    #                 partners = self.env['res.partner'].search([("name","ilike",fournisseur)])
    #                 for partner in partners:
    #                     partner_id = partner.id
    #                 if partner_id==False:
    #                     vals={
    #                         "name"           : fournisseur,
    #                         "is_code_interne": "CREATION",
    #                     }
    #                     partner=self.env['res.partner'].create(vals)
    #                     print("CREATION ",partner)
    #                     partner_id = partner.id
    #             #**********************************************************


    #             if code and designation and prix and partner_id:
    #                 filtre=[("default_code","=",code)]
    #                 products = self.env['product.template'].search(filtre)
    #                 vals={
    #                     "name"                  : designation,
    #                     "default_code"          : code,
    #                     "list_price"            : 0,
    #                     "is_nb_pieces_par_colis": colisage,
    #                     "is_poids_net_colis"    : poids,
    #                     "taxes_id"              : [(6, 0, [taxe_vente_id])],
    #                     "supplier_taxes_id"     : [(6, 0, [taxe_achat_id])],
    #                     "type"                  : "product",
    #                 }
    #                 if kg_piece=="K":
    #                     vals["uom_id"]    = uom_id
    #                     vals["uom_po_id"] = uom_id
                    
    #                 if len(products)==0:
    #                     product=self.env['product.template'].create(vals)
    #                 else:
    #                     product = products[0]
    #                     #product.write(vals)

    #                 print(ct,product,code,kg_piece,prix,designation)

    #                 #** Création ligne tarif fournisseur ******************
    #                 vals={
    #                     "product_tmpl_id": product.id,
    #                     "name"           : partner_id,
    #                     "min_qty"        : 1,
    #                     "prix_brut"      : prix,
    #                     "date_start"     : "2022-01-01",
    #                     "date_end"       : "2032-01-01",
    #                 }
    #                 filtre=[("product_tmpl_id","=",product.id)]
    #                 supplierinfos = self.env['product.supplierinfo'].search(filtre)
    #                 if len(supplierinfos)==0:
    #                     supplierinfo=self.env['product.supplierinfo'].create(vals)
    #                     #print("Create supplierinfo", supplierinfo )
    #                 else:
    #                     supplierinfo = supplierinfos[0]
    #                     supplierinfo.write(vals)
    #                     #print("Write supplierinfo", supplierinfo )
    #                 ct+=1
    #             lig+=1

    #             # if ct>100:
    #             #    break


    #         self.create_pricelist(wb, "HT 2022"    , "TARIF HORS TRANSPORT")
    #         self.create_pricelist(wb, "FRANCO 2022", "FRANCO DE PORT")



