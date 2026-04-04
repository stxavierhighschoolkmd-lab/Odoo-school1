import { expect, test } from "@odoo/hoot";
import { ForecastedDetails } from "@stock/stock_forecasted/forecasted_details";

test("forecast detail sameDocument receipt date", async () => {
    const forecast = new ForecastedDetails(null, {});
    const doc = { id: 10, _name: "stock.picking", name: "PICK/001" };

    const line1 = { document_in: { ...doc }, receipt_date: "2024-01-01" };
    const line2 = { document_in: { ...doc }, receipt_date: "2024-01-01" };
    expect(forecast._sameDocument(line1, line2, "document_in")).toBe(true);

    const line3 = { document_in: { ...doc }, receipt_date: "2024-01-01" };
    const line4 = { document_in: { ...doc }, receipt_date: "2024-01-03" };
    expect(forecast._sameDocument(line3, line4, "document_in")).toBe(false);
});
