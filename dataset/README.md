# ContosoRetail Dataset

Synthetic 13-table Power BI push dataset for NL2Query evaluation. Deterministically generated (seed=42).

## Usage

```bash
pip install requests faker
az login
python build_contoso_dataset.py <workspace_id> [tenant_id]
```

Output: `dataset_id.txt` — the new dataset ID, read by `/tabletalk-fabric-deploy` and `/fabric-analyst-deploy`.

## Tables

| Table | Rows | Key columns |
|---|---|---|
| dim_customers | 500 | customer_id, customer_segment (New/Regular/VIP/At-Risk), lifetime_value |
| dim_products | 500 | product_id, category, unit_cost, unit_price, margin_pct |
| dim_stores | 500 | store_id, region (North/South/East/West/Southwest/Midwest) |
| dim_employees | 500 | employee_id, department, performance_rating |
| fact_orders | 500 | order_id, customer_id, store_id, order_value, channel |
| fact_order_items | 500 | order_item_id, order_id, product_id, quantity |
| fact_returns | 500 | return_id, order_item_id, return_reason |
| fact_inventory | 500 | store_id, product_id, stock_level, stockout_flag |
| fact_marketing_campaigns | 500 | campaign_id, channel, roi, net_revenue_lift |
| fact_website_sessions | 500 | session_id, customer_id, conversion_flag |
| fact_support_tickets | 500 | ticket_id, customer_id, issue_category |
| fact_supplier_performance | 500 | supplier_id, on_time_flag, quality_score, po_value |
| fact_store_traffic | 500 | store_id, visitor_count, conversion_rate |

**Important:** Push dataset — **no active relationships**. All cross-table joins require `SUMX(FILTER())`.
