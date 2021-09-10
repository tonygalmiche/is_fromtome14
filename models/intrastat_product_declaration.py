from odoo import api, fields, models, _
import odoo.addons.decimal_precision as dp
from lxml import etree
from odoo.exceptions import Warning
import logging
_logger = logging.getLogger(__name__)

# class L10nFrIntrastatProductDeclarationLine(models.Model):
#     _inherit = 'l10n.fr.intrastat.product.declaration.line'
#

class L10nFrIntrastatProductComputationLine(models.Model):
    _inherit = 'l10n.fr.intrastat.product.computation.line'
    weight = fields.Float(
        string='Nb Unités',
        digits=dp.get_precision('Stock Weight'), help="Quantité en pièce ou  Kg")
    weight_net = fields.Float(
        string='Masse en kg',
        digits=dp.get_precision('Stock Weight'), help="Poids net en Kg")
    date_invoice = fields.Date('Date')

class IntrastatProductComputationLine(models.Model):
    _inherit = 'intrastat.product.computation.line'
    weight = fields.Float(
        string='Nb Unités',
        digits=dp.get_precision('Stock Weight'), help="Quantité en pièce ou  Kg")
    weight_net = fields.Float(
        string='Masse en kg',
        digits=dp.get_precision('Stock Weight'), help="Poids net en Kg")
    date_invoice = fields.Date('Date')

class IntrastatProductDeclarationLine(models.Model):
    _inherit = 'intrastat.product.declaration.line'

    weight = fields.Integer(
        string='Nb Unités', help="Quantité en pièce ou  Kg")
    weight_net = fields.Integer(
        string='Masse en kg', help="Poids net en Kg")
    date_invoice = fields.Date('Date')

class IntrastatProductDeclaration(models.Model):
    _inherit = 'intrastat.product.declaration'

    def _get_weight_and_supplunits(self, inv_line, hs_code):
        line_qty = inv_line.quantity
        product = inv_line.product_id
        invoice = inv_line.invoice_id
        intrastat_unit_id = hs_code.intrastat_unit_id
        source_uom = inv_line.uom_id
        weight_uom_categ = self._get_uom_refs('weight_uom_categ')
        kg_uom = self._get_uom_refs('kg_uom')
        pce_uom_categ = self._get_uom_refs('pce_uom_categ')
        pce_uom = self._get_uom_refs('pce_uom')
        volume_uom_categ = self._get_uom_refs('volume_uom_categ')
        m3_uom = self._get_uom_refs('m3_uom')
        weight = suppl_unit_qty = 0.0
        weight_net  = 0.0
        if not source_uom:
            note = "\n" + _(
                "Missing unit of measure on the line with %d "
                "product(s) '%s' on invoice '%s'."
            ) % (line_qty, product.name_get()[0][1], invoice.number)
            note += "\n" + _(
                "Please adjust this line manually.")
            self._note += note
            return weight, suppl_unit_qty

        if intrastat_unit_id:
            target_uom = intrastat_unit_id.uom_id
            if not target_uom:
                note = "\n" + _(
                    "Conversion from Intrastat Supplementary Unit '%s' to "
                    "Unit of Measure is not implemented yet."
                ) % intrastat_unit_id.name
                note += "\n" + _(
                    "Please correct the Intrastat Supplementary Unit "
                    "settings and regenerate the lines or adjust the lines "
                    "with Intrastat Code '%s' manually"
                ) % hs_code.display_name
                self._note += note
                #print('1weight--',weight)
                return weight, suppl_unit_qty
            if target_uom.category_id == source_uom.category_id:
                suppl_unit_qty = source_uom._compute_quantity(
                    line_qty, target_uom)
            elif target_uom.category_id == volume_uom_categ:
                # in case of product records with the volume field
                # correctly filled in we should report back this
                # volume (converted to the target_uom)
                if not product.volume:
                    note = "\n" + _(
                        "Product '%s' has an Intrastat Supplementary Unit "
                        "in the 'volume' Unit of Measure (UoM) category. "
                        "The Supplementary Unit Quantity calculation "
                        "has failed since the product "
                        "has been sold/purchased with a UoM without "
                        "volume conversion. "
                        "There is also no 'volume' specificied on the "
                        "product record which also allows to calculate the "
                        "Intrastat Supplementary Unit."
                    ) % product.name_get()[0][1]
                    note += "\n" + _(
                        "Please correct the product record and regenerate "
                        "the lines or adjust the impacted lines manually")
                    self._note += note
                    #print('2weight--', weight)
                    return weight, suppl_unit_qty
                suppl_unit_qty = m3_uom._compute_quantity(
                    line_qty * product.volume, target_uom)
            else:
                note = "\n" + _(
                    "Conversion from unit of measure '%s' to '%s' "
                    "is not implemented yet."
                ) % (source_uom.name, target_uom.name)
                note += "\n" + _(
                    "Please correct the unit of measure settings and "
                    "regenerate the lines or adjust the impacted "
                    "lines manually")
                self._note += note
                #print('3weight--', weight)
                return weight, suppl_unit_qty

        if source_uom == kg_uom:
            #print('4weight--', weight)
            weight = line_qty
            weight_net = line_qty
        elif source_uom.category_id == weight_uom_categ:
            #print('5weight--', weight)
            weight = source_uom._compute_quantity(line_qty, kg_uom)
        elif source_uom.category_id == pce_uom_categ:
            if not product.weight:  # re-create weight_net ?
                note = "\n" + _(
                    "Missing weight on product %s."
                ) % product.name_get()[0][1]
                note += "\n" + _(
                    "Please correct the product record and regenerate "
                    "the lines or adjust the impacted lines manually")
                self._note += note
                #print('6weight--', weight)
                return weight, suppl_unit_qty
            if source_uom == pce_uom:
                weight = product.weight * line_qty  # product.weight_net
            else:
                # Here, I suppose that, on the product, the
                # weight is per PCE and not per uom_id
                # product.weight_net
                weight = product.weight * \
                         source_uom._compute_quantity(line_qty, pce_uom)
        else:
            # in case of product records with e.g. uom 'liter' and the weight
            # correctly filled in we should report back the weight
            if not product.weight:
                note = "\n" + _(
                    "Missing weight on product %s."
                ) % product.name_get()[0][1]
                note += "\n" + _(
                    "Please correct the product record and regenerate "
                    "the lines or adjust the impacted lines manually")
                self._note += note
                #print('7weight--', weight)
                return weight, suppl_unit_qty
            qty = source_uom._compute_quantity(
                line_qty, product.uom_id, raise_if_failure=False)
            weight = product.weight * qty

        if weight_net == 0 and source_uom != kg_uom :
            weight_net = (product.product_weight / product.weight)*line_qty
        #print('8weight--', weight)
        #print('weight_net----',weight_net)
        #print('line_qty--',line_qty)
        return weight, suppl_unit_qty,weight_net


    def _gather_invoices(self):

        lines = []
        accessory_costs = self.company_id.intrastat_accessory_costs

        self._gather_invoices_init()
        domain = self._prepare_invoice_domain()
        invoices = self.env['account.invoice'].search(domain)

        for invoice in invoices:
            lines_current_invoice = []
            total_inv_accessory_costs_cc = 0.0  # in company currency
            total_inv_product_cc = 0.0  # in company currency
            total_inv_weight = 0.0
            for inv_line in invoice.invoice_line_ids:

                if (
                        accessory_costs and
                        inv_line.product_id and
                        inv_line.product_id.is_accessory_cost):
                    acost = invoice.currency_id._convert(
                        inv_line.price_subtotal,
                        self.company_id.currency_id,
                        self.company_id,
                        invoice.date_invoice)
                    total_inv_accessory_costs_cc += acost

                    continue

                if not inv_line.quantity:
                    _logger.info(
                        'Skipping invoice line %s qty %s '
                        'of invoice %s. Reason: qty = 0'
                        % (inv_line.name, inv_line.quantity, invoice.number))
                    continue
                partner_country = self._get_partner_country(inv_line)
                if not partner_country:
                    _logger.info(
                        'Skipping invoice line %s qty %s '
                        'of invoice %s. Reason: no partner_country'
                        % (inv_line.name, inv_line.quantity, invoice.number))
                    continue

                if any([
                        tax.exclude_from_intrastat_if_present
                        for tax in inv_line.invoice_line_tax_ids]):
                    _logger.info(
                        'Skipping invoice line %s '
                        'qty %s of invoice %s. Reason: '
                        'tax.exclude_from_intrastat_if_present'
                        % (inv_line.name, inv_line.quantity, invoice.number))
                    continue

                if inv_line.hs_code_id:
                    hs_code = inv_line.hs_code_id
                elif inv_line.product_id and self._is_product(inv_line):
                    hs_code = inv_line.product_id.get_hs_code_recursively()
                    if not hs_code:
                        note = "\n" + _(
                            "Missing H.S. code on product %s. "
                            "This product is present in invoice %s.") % (
                                inv_line.product_id.name_get()[0][1],
                                inv_line.invoice_id.number)
                        self._note += note
                        continue
                else:
                    _logger.info(
                        'Skipping invoice line %s qty %s '
                        'of invoice %s. Reason: no product nor hs_code'
                        % (inv_line.name, inv_line.quantity, invoice.number))
                    continue

                intrastat_transaction = \
                    self._get_intrastat_transaction(inv_line)

                print('#TEST',invoice,invoice.number)
                try:
                    weight, suppl_unit_qty, weight_net = self._get_weight_and_supplunits(inv_line, hs_code)
                except ValueError:
                    raise Warning("Problème avec la facture "+str(invoice.number))

                total_inv_weight += weight_net

                amount_company_currency = self._get_amount(inv_line)
                total_inv_product_cc += amount_company_currency

                product_origin_country = self._get_product_origin_country(
                    inv_line)

                region = self._get_region(inv_line)

                line_vals = {
                    'parent_id': self.id,
                    'invoice_line_id': inv_line.id,
                    'src_dest_country_id': partner_country.id,
                    'product_id': inv_line.product_id.id,
                    'hs_code_id': hs_code.id,
                    'weight': weight,
                    'weight_net': weight_net,
                    'suppl_unit_qty': suppl_unit_qty,
                    'amount_company_currency': amount_company_currency,
                    'amount_accessory_cost_company_currency': 0.0,
                    'transaction_id': intrastat_transaction.id,
                    'product_origin_country_id':
                    product_origin_country.id or False,
                    'region_id': region and region.id or False,
                    'date_invoice': invoice.date_invoice,
                }

                # extended declaration
                if self._extended:
                    transport = self._get_transport(inv_line)
                    line_vals.update({
                        'transport_id': transport.id,
                    })

                self._update_computation_line_vals(inv_line, line_vals)

                if line_vals:
                    lines_current_invoice.append((line_vals))

            self._handle_invoice_accessory_cost(
                invoice, lines_current_invoice,
                total_inv_accessory_costs_cc, total_inv_product_cc,
                total_inv_weight)

            for line_vals in lines_current_invoice:
                if (
                        not line_vals['amount_company_currency'] and
                        not
                        line_vals['amount_accessory_cost_company_currency']):
                    inv_line = self.env['account.invoice.line'].browse(
                        line_vals['invoice_line_id'])
                    _logger.info(
                        'Skipping invoice line %s qty %s '
                        'of invoice %s. Reason: price_subtotal = 0 '
                        'and accessory costs = 0'
                        % (inv_line.name, inv_line.quantity,
                           inv_line.invoice_id.number))
                    continue
                lines.append(line_vals)
        return lines


    def _fields_to_sum(self):
        fields_to_sum = [
            'weight',
            'suppl_unit_qty',
            'weight_net',
            ]
        return fields_to_sum

class L10nFrIntrastatProductDeclaration(models.Model):
    _inherit = "l10n.fr.intrastat.product.declaration"
    #
    # @api.model
    # def _prepare_grouped_fields(self, computation_line, fields_to_sum):
    #     vals = super(L10nFrIntrastatProductDeclaration, self). \
    #         _prepare_grouped_fields(computation_line, fields_to_sum)
    #     vals['weight_net'] = computation_line.weight_net
    #     return vals

    @api.model
    def _xls_template(self):
        res = super(L10nFrIntrastatProductDeclaration, self)._xls_template()
        print('weighhghgt---', self._render(
                        'line.weight_net'))
        res.update({
            'weight_net': {
                'header': {
                    'type': 'string',
                    'value': self._('Mass en KG'),
                    # 'format': self.format_theader_yellow_right,
                },
                'line': {
                    'type': 'number',
                    'value': self._render(
                        "line.weight_net"),
                    # 'format': self.format_tcell_amount_right,
                },
                'width': 18,
            },
            'date_invoice': {
                'header': {
                    'type': 'string',
                    'value': self._('Date'),
                },
                'line': {
                    # 'type': 'Date',
                    'value': self._render(
                        "line.date_invoice"),
                },
                'width': 18,


            },
        })
        return res

    @api.model
    def _xls_computation_line_fields(self):
        field_list = super(L10nFrIntrastatProductDeclaration, self). \
            _xls_computation_line_fields()
        field_list += ['weight_net','date_invoice']
        return field_list

    @api.model
    def _xls_declaration_line_fields(self):
        field_list = super(L10nFrIntrastatProductDeclaration, self). \
            _xls_declaration_line_fields()
        field_list += ['weight_net']
        return field_list


    @api.model
    def _update_computation_line_vals(self, inv_line, line_vals):
        super(L10nFrIntrastatProductDeclaration, self). \
            _update_computation_line_vals(
            inv_line, line_vals)
        inv = inv_line.invoice_id
        line_vals['date_invoice'] = inv.date_invoice

