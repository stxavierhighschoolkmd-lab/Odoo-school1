PEPPOL_COMMON_OPTIONAL_FIELDS = {
    "x_studio_peppol_tax_point_date": {
        "path": ["cbc:TaxPointDate"],
        "attrs": lambda invoice: {
            "_text": invoice.x_studio_peppol_tax_point_date,
        },
    },
    "x_studio_peppol_contract_document_reference_id": {
        "path": ["cac:ContractDocumentReference", "cbc:ID"],
        "attrs": lambda invoice: {
            '_text': invoice.x_studio_peppol_contract_document_reference_id,
        },
    },
    "x_studio_peppol_despatch_document_reference_id": {
        "path": ["cac:DespatchDocumentReference", "cbc:ID"],
        "attrs": lambda invoice: {
            '_text': invoice.x_studio_peppol_despatch_document_reference_id,
        },
    },
    "x_studio_peppol_accounting_cost": {
        "path": ["cbc:AccountingCost"],
        "attrs": lambda invoice: {
            '_text': invoice.x_studio_peppol_accounting_cost,
        },
    },
    # BACKPORT: WE NEED TO OVERRIDE THE STANDARD VALS INSTEAD OF CREATE THE ELEMENT
    "x_studio_peppol_order_reference_id": {
        "path": None,
        "native_key": "order_reference",
        "attrs": lambda invoice: invoice.x_studio_peppol_order_reference_id,
    },
    "x_studio_peppol_invoice_period_start_date": {
        "path": ["cac:InvoicePeriod", "cbc:StartDate"],
        "attrs": lambda invoice: {
            '_text': invoice.x_studio_peppol_invoice_period_start_date,
        }
    },
    "x_studio_peppol_invoice_period_end_date": {
        "path": ["cac:InvoicePeriod", "cbc:EndDate"],
        "attrs": lambda invoice: {
            '_text': invoice.x_studio_peppol_invoice_period_end_date,
        }
    },
}

PEPPOL_INVOICE_OPTIONAL_FIELDS = {
    **PEPPOL_COMMON_OPTIONAL_FIELDS,
    "x_studio_peppol_project_reference_id": {
        "path": ["cac:ProjectReference", "cbc:ID"],
        "attrs": lambda invoice: {
            '_text': invoice.x_studio_peppol_project_reference_id,
        },
    },
}

PEPPOL_CREDIT_NOTE_OPTIONAL_FIELDS = {
    **PEPPOL_COMMON_OPTIONAL_FIELDS,
}

# BACKPORT: ADDED TARGET BECAUSE WE NEED TO KNOW IF IS INSIDE OR OUTSIDE cac:Item
# line -> outside, item -> inside
PEPPOL_COMMON_OPTIONAL_LINE_FIELDS = {
    "x_studio_peppol_order_line_reference_id": {
        "path": ["cac:OrderLineReference", "cbc:LineID"],
        "target": "line",
        "attrs": lambda line: {
            '_text': line.x_studio_peppol_order_line_reference_id,
        }
    },
    "x_studio_peppol_buyers_item_id": {
        "path": ["cac:BuyersItemIdentification", "cbc:ID"],
        "target": "item",
        "attrs": lambda line: {
            '_text': line.x_studio_peppol_buyers_item_id,
        }
    },
}

PEPPOL_INVOICE_OPTIONAL_LINE_FIELDS = {
    **PEPPOL_COMMON_OPTIONAL_LINE_FIELDS,
}

PEPPOL_CREDIT_NOTE_OPTIONAL_LINE_FIELDS = {
    **PEPPOL_COMMON_OPTIONAL_LINE_FIELDS,
}
