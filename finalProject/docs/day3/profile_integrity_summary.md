# Profile and integrity summary (Day 3)

- **Generated (UTC):** 2026-04-18T04:12:42Z

## Full-file profile

### BOM.csv
rows=87,059  cols=3

mother                              str
child                               str
individual_input_quantity_q_mc    int64

Null counts: none

Distinct counts:
  mother: 28,049
  child: 49
  individual_input_quantity_q_mc: 4

### arcs.csv
rows=11  cols=4

starting_node_i             str
ending_node_j               str
process_lead_time_l_ij    int64
group_g                     str

Null counts: none

Distinct counts:
  starting_node_i: 11
  ending_node_j: 8
  process_lead_time_l_ij: 5
  group_g: 7

### capacity_at_arc.csv
rows=154  cols=4

starting_node_i      str
ending_node_j        str
period_t           int64
capacity_c_ijt     int64

Null counts: none

Distinct counts:
  starting_node_i: 11
  ending_node_j: 8
  period_t: 14
  capacity_c_ijt: 6
  period_t range: 61 … 74

### demands.csv
rows=28,000  cols=4

node_n            str
product_p       int64
demand_d_npt    int64
period_t        int64

Null counts: none

Distinct counts:
  node_n: 1
  product_p: 28,000
  demand_d_npt: 1
  period_t: 14
  period_t range: 61 … 74

### initial_flows.csv
rows=117  cols=5

starting_node_i      str
ending_node_j        str
product_p            str
period_t           int64
initial_flow       int64

Null counts: none

Distinct counts:
  starting_node_i: 8
  ending_node_j: 6
  product_p: 45
  period_t: 5
  initial_flow: 99
  period_t range: 39 … 60

### initial_inventories.csv
rows=82  cols=6

node_n                       str
product_p                    str
initial_inventory_I_np0    int64
safety_stock               int64
max_inventory              int64
period_t                   int64

Null counts: none

Distinct counts:
  node_n: 5
  product_p: 45
  initial_inventory_I_np0: 72
  safety_stock: 1
  max_inventory: 1
  period_t: 1
  period_t range: 60 … 60

### max_flow_group_per_arc.csv
rows=20  cols=5

starting_node_i      str
ending_node_j        str
group_g              str
period_t           int64
planned_flow       int64

Null counts: none

Distinct counts:
  starting_node_i: 2
  ending_node_j: 2
  group_g: 2
  period_t: 10
  planned_flow: 1
  period_t range: 61 … 70

### max_flow_product_per_arc.csv
rows=365  cols=5

starting_node_i      str
ending_node_j        str
product_p            str
period_t           int64
planned_flow       int64

Null counts: none

Distinct counts:
  starting_node_i: 2
  ending_node_j: 2
  product_p: 37
  period_t: 10
  planned_flow: 180
  period_t range: 61 … 70

### nodes.csv
rows=12  cols=1

node_n    str

Null counts: none

Distinct counts:
  node_n: 12

### nodes_inflow.csv
rows=44  cols=2

node_n       str
product_p    str

Null counts: none

Distinct counts:
  node_n: 4
  product_p: 44

### operations.csv
rows=15  cols=7

node_n                       str
input_product_group_x        str
output_product_group_y       str
input_quantity_in_nxy      int64
output_quantity_out_nxy    int64
alpha_nxy                  int64
beta_nxy                   int64

Null counts: none

Distinct counts:
  node_n: 12
  input_product_group_x: 7
  output_product_group_y: 7
  input_quantity_in_nxy: 2
  output_quantity_out_nxy: 1
  alpha_nxy: 1
  beta_nxy: 2

### products.csv
rows=28,049  cols=3

product_p                  str
group_g                    str
transportation_size_s    int64

Null counts: none

Distinct counts:
  product_p: 28,049
  group_g: 7
  transportation_size_s: 1

## Cross-table integrity

INFO BOM.child: 49 distinct child codes; 0 appear as stringified products.product_p (rest are part codes only in BOM)
INFO initial_inventories.product_p: 45 distinct symbols; 0 match stringified numeric products (others e.g. BEV-style codes — still model as :Product)