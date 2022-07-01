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
            print(obj)

            for attachment in obj.file_ids:
                xlsxfile=base64.b64decode(attachment.datas)

                path = '/tmp/is_import_le_cellier-'+str(obj.id)+'.xlsx'
                f = open(path,'wb')
                f.write(xlsxfile)
                f.close()

                #** Test si fichier est bien du xlsx *******************************
                try:
                    wb    = openpyxl.load_workbook(filename = path, data_only=True)
                    ws    = wb.active
                    cells = list(ws)
                except:
                    raise Warning("Le fichier "+attachment.name+u" n'est pas un fichier xlsx")
                #*******************************************************************

                lig=ct=0
                for row in ws.rows:
                    code        = cells[lig][1].value
                    designation = cells[lig][2].value
                    designation = cells[lig][2].value
                    colisage    = xls2float(cells[lig][6].value)
                    poids       = xls2float(cells[lig][7].value)
                    prix        = xls2float(cells[lig][10].value)
                    kg_piece    = cells[lig][31].value
                    if code and designation and prix:
                        filtre=[("default_code","=",code)]
                        products = self.env['product.template'].search(filtre)
                        vals={
                            "name"                  : designation,
                            "default_code"          : code,
                            "list_price"            : prix,
                            "is_nb_pieces_par_colis": colisage,
                            "is_poids_net_colis"    : poids,
                        }
                        if len(products)==0:
                            product=self.env['product.template'].create(vals)
                        else:
                            product = products[0]
                            product.write(vals)

                        print(ct,product,code,kg_piece,prix,designation)
                        ct+=1
                    lig+=1

                    # if ct>10:
                    #     break
