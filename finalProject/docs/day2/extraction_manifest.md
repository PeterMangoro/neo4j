# Extraction manifest

- **Generated (UTC):** 2026-04-18T04:12:40Z
- **Python:** 3.13.9
- **pyxlsb:** 1.0.10
- **Workbook:** `2020_dataset_OfAutomotiveProductionNetwork.xlsb`

| Sheet key | Rows | Cols | Columns |
|-----------|------|------|---------|
| BOM | 87,059 | 3 | mother, child, individual_input_quantity_q_mc |
| arcs | 11 | 4 | starting_node_i, ending_node_j, process_lead_time_l_ij, group_g |
| capacity_at_arc | 154 | 4 | starting_node_i, ending_node_j, period_t, capacity_c_ijt |
| demands | 28,000 | 4 | node_n, product_p, demand_d_npt, period_t |
| initial_flows | 117 | 5 | starting_node_i, ending_node_j, product_p, period_t, initial_flow |
| initial_inventories | 82 | 6 | node_n, product_p, initial_inventory_I_np0, safety_stock, max_inventory, period_t |
| max_flow_group_per_arc | 20 | 5 | starting_node_i, ending_node_j, group_g, period_t, planned_flow |
| max_flow_product_per_arc | 365 | 5 | starting_node_i, ending_node_j, product_p, period_t, planned_flow |
| nodes | 12 | 1 | node_n |
| nodes_inflow | 44 | 2 | node_n, product_p |
| operations | 15 | 7 | node_n, input_product_group_x, output_product_group_y, input_quantity_in_nxy, output_quantity_out_nxy, alpha_nxy, beta_nxy |
| products | 28,049 | 3 | product_p, group_g, transportation_size_s |
