import json
import requests

from odoo import models, fields
from odoo.tools import html_escape, zeep
from odoo.addons.certificate.tools import CertificateAdapter

EUSKADI_CIPHERS = "DEFAULT:!DH"

AEAT_BASE_URL = "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/ssii_1_1/fact/ws"
AEAT_TEST_BASE_URL = "https://prewww1.aeat.es/wlpl/SSII-FACT/ws"

BIZKAIA_BASE_URL = "https://www.bizkaia.eus/ogasuna/sii/documentos"
BIZKAIA_TEST_BASE_URL = "https://pruapps.bizkaia.eus/SSII-FACT/ws"

GIPUZKOA_BASE_URL = "https://egoitza.gipuzkoa.eus/ogasuna/sii/ficheros/v1.1"
GIPUZKOA_TEST_BASE_URL = "https://sii-prep.egoitza.gipuzkoa.eus/JBS/HACI/SSII-FACT/ws"


class L10nEsEdiSiiDocument(models.Model):
    _name = 'l10n_es_edi_sii.document'
    _description = 'SII Document'
    _order = 'create_date desc'

    move_id = fields.Many2one(
        comodel_name='account.move',
        required=True,
        ondelete='cascade',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        related='move_id.company_id',
    )
    is_cancel = fields.Boolean(
        string="Is a Cancellation",
    )
    state = fields.Selection(
        selection=[
            ('to_send', "To Send"),
            ('accepted', "Accepted"),
            ('accepted_with_errors', "Accepted with Errors"),
            ('rejected', "Rejected"),
            ('cancelled', "Cancelled"),
        ],
        string="State",
        default='to_send',
        required=True,
    )
    csv = fields.Char(
        string="CSV",
        copy=False,
        help="Secure Verification Code returned by the SII",
    )
    attachment_id = fields.Many2one(
        comodel_name='ir.attachment',
        string="SII JSON Payload",
        ondelete='restrict',
        help="The full JSON payload (Header + Body) sent to the SII.",
    )
    response_message = fields.Html(
        string="Response",
    )

    # -------------------------------------------------------------------------
    # HELPER METHODS
    # -------------------------------------------------------------------------

    def _get_attachment_name(self):
        self.ensure_one()
        return f"sii_{self.move_id.name.replace('/', '_')}_{self.id}.json"

    def action_download_json(self):
        self.ensure_one()

        if not self.attachment_id:
            communication_type = 'A1' if self.move_id.l10n_es_edi_csv and not self.is_cancel else 'A0'
            header = {
                'IDVersionSii': '1.1',
                'Titular': {
                    'NombreRazon': self.company_id.name[:120],
                    'NIF': self.company_id.vat[2:] if self.company_id.vat.startswith('ES') else self.company_id.vat,
                },
                'TipoComunicacion': communication_type,
            }
            info_list = self.move_id._l10n_es_edi_get_invoices_info()
            self._generate_json(header, info_list)

        if self.attachment_id:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{self.attachment_id.id}?download=true',
                'target': 'self',
            }
        return False

    def _get_agency_urls(self):
        agency = self.company_id.l10n_es_sii_tax_agency
        is_sale = self.move_id.is_sale_document()
        if agency == "aeat":
            return {
                "url": f"{AEAT_BASE_URL}/SuministroFact{'Emitidas' if is_sale else 'Recibidas'}.wsdl",
                "test_url": f"{AEAT_TEST_BASE_URL}/{'fe/SiiFactFEV1SOAP' if is_sale else 'fr/SiiFactFRV1SOAP'}",
            }
        if agency == "bizkaia":
            return {
                "url": f"{BIZKAIA_BASE_URL}/SuministroFact{'Emitidas' if is_sale else 'Recibidas'}.wsdl",
                "test_url": f"{BIZKAIA_TEST_BASE_URL}/{'fe/SiiFactFEV1SOAP' if is_sale else 'fr/SiiFactFRV1SOAP'}",
            }
        elif agency == "gipuzkoa":
            return {
                "url": f"{GIPUZKOA_BASE_URL}/SuministroFact{'Emitidas' if is_sale else 'Recibidas'}.wsdl",
                "test_url": f"{GIPUZKOA_TEST_BASE_URL}/{'fe/SiiFactFEV1SOAP' if is_sale else 'fr/SiiFactFRV1SOAP'}",
            }
        return {}

    def _generate_json(self, header, info_list):
        self.ensure_one()
        full_payload = {
            'Cabecera': header,
            'Cuerpo': info_list,
        }
        attachment = self.env['ir.attachment'].sudo().create({
            'name': self._get_attachment_name(),
            'raw': json.dumps(full_payload, indent=4).encode('utf-8'),
            'mimetype': 'application/json',
            'res_model': 'account.move',
            'res_id': self.move_id.id,
        })
        self.sudo().write({'attachment_id': attachment.id})

    # -------------------------------------------------------------------------
    # WEB SERVICE LOGIC
    # -------------------------------------------------------------------------

    def _post_to_web_service(self, info_list, communication_type='A0'):
        """ Equivalent to TBAI's _post_to_web_service. Orchestrates the WS call for this document. """
        self.ensure_one()
        company = self.company_id

        header = {
            'IDVersionSii': '1.1',
            'Titular': {
                'NombreRazon': company.name[:120],
                'NIF': company.vat[2:] if company.vat.startswith('ES') else company.vat,
            },
            'TipoComunicacion': communication_type,
        }

        success, response_data = self._post_to_agency(header, info_list)

        if response_data.get('error_1117'):
            return {'error_1117': True}

        if success:
            state = 'cancelled' if self.is_cancel else 'accepted'
            if response_data.get('accepted_with_errors'):
                state = 'accepted_with_errors'

            self._generate_json(header, info_list)

            self.sudo().write({
                'state': state,
                'csv': response_data.get('csv'),
                'response_message': response_data.get('response_message', 'Success'),
            })
        else:
            self.sudo().write({
                'state': 'rejected',
                'response_message': response_data.get('response_message', 'Unknown Error'),
            })

        return {'success': success, 'state': self.state}

    def _post_to_agency(self, header, info_list):
        self.ensure_one()
        company = self.company_id
        connection_vals = self._get_agency_urls()

        with requests.Session() as session:
            try:
                session.cert = company.l10n_es_sii_certificate_id
                session.mount('https://', CertificateAdapter(ciphers=EUSKADI_CIPHERS))

                client = zeep.Client(connection_vals['url'], operation_timeout=60, timeout=60, session=session)

                is_sale = self.move_id.is_sale_document()
                service_name = 'SuministroFactEmitidas' if is_sale else 'SuministroFactRecibidas'
                if company.l10n_es_sii_test_env and not connection_vals.get('test_url'):
                    service_name += 'Pruebas'

                serv = client.bind('siiService', service_name)
                if company.l10n_es_sii_test_env and connection_vals.get('test_url'):
                    serv._binding_options['address'] = connection_vals['test_url']

                if self.is_cancel:
                    if is_sale:
                        res = serv.AnulacionLRFacturasEmitidas(header, info_list)
                    else:
                        res = serv.AnulacionLRFacturasRecibidas(header, info_list)
                else:
                    if is_sale:
                        res = serv.SuministroLRFacturasEmitidas(header, info_list)
                    else:
                        res = serv.SuministroLRFacturasRecibidas(header, info_list)

            except requests.exceptions.SSLError:
                return False, {'response_message': self.env._("The SSL certificate could not be validated.")}
            except (zeep.exceptions.Error, requests.exceptions.ConnectionError) as error:
                return False, {'response_message': self.env._("Networking error:\n%s", error)}
            except Exception as error:  # noqa: BLE001
                return False, {'response_message': str(error)}

        if not res or not res.RespuestaLinea:
            return False, {'response_message': self.env._("The web service is not responding")}

        return self._process_response(res)

    def _process_response(self, res):
        resp_state = res["EstadoEnvio"]
        csv_number = res['CSV']

        if resp_state == 'Correcto':
            return True, {'csv': csv_number, 'response_message': 'Correcto'}

        for respl in res.RespuestaLinea:
            resp_line_state = respl.EstadoRegistro
            respl_dict = dict(respl)

            if resp_line_state == 'Correcto':
                return True, {'csv': csv_number, 'response_message': 'Correcto'}

            elif resp_line_state == 'AceptadoConErrores':
                return True, {
                    'csv': csv_number,
                    'accepted_with_errors': True,
                    'response_message': self.env._("Accepted with errors: %s", html_escape(respl.DescripcionErrorRegistro))
                }

            elif (
                (respl_dict.get('RegistroDuplicado') and respl.RegistroDuplicado.EstadoRegistro == 'Correcta')
                or
                (self.is_cancel and respl_dict.get('CodigoErrorRegistro') == 3001)
            ):
                return True, {
                    'csv': csv_number or self.move_id.l10n_es_edi_csv,
                    'response_message': self.env._("Duplicated/Already processed.")
                }

            elif respl.CodigoErrorRegistro == 1117 and not self.env.context.get('error_1117'):
                return False, {'error_1117': True}

            else:
                return False, {
                    'response_message': self.env._("[%(error_code)s] %(error_message)s",
                                        error_code=respl.CodigoErrorRegistro,
                                        error_message=respl.DescripcionErrorRegistro)
                }

        return False, {'response_message': self.env._("Unknown response state")}
