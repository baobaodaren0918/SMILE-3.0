// Neo4j Graph Schema: Northwind V2 (G2G Evolution Target)
// 9 nodes, 9 relationships
// categories MERGED into products, PART_OF deleted
// customers SPLIT -> customers + contact, HAS_CONTACT added
// sales_region + territories added, BELONGS_TO + ASSIGNED_TO added

// Node: suppliers:Vendor
// Key: supplier_id
// Properties: supplier_id (string), company_name (string), contact_name (string), contact_title (string), phone (string), fax (string), street (string), city (string), region (string), postal_code (string), country (string)

// Node: shippers
// Key: shipper_id
// Properties: shipper_id (string), company_name (string), phone (string)

// Node: employees
// Key: employee_id
// Properties: employee_id (string), last_name (string), first_name (string), title (string), hire_date (date), phone (string), street (string), city (string), region (string), postal_code (string), country (string), email (string)

// Node: customers
// Key: customer_id
// Properties: customer_id (string), company_name (string), street (string), city (string), region (string), postal_code (string), country (string)

// Node: products
// Key: product_id
// Properties: product_id (string), name (string), unit_price (double), units_in_stock (integer), discontinued (boolean), quantity_per_unit (string), category_name (string), description (string)

// Node: orders
// Key: order_id
// Properties: order_id (string), order_date (date), required_date (date), shipped_date (date), shipping_cost (double), ship_name (string), ship_address (string), ship_city (string), ship_region (string), ship_postal_code (string), ship_country (string), status (string)

// Node: contact
// Key: contact_id
// Properties: contact_id (string), customer_id (string), contact_name (string), contact_title (string), phone (string), fax (string)

// Node: sales_region
// Key: region_id
// Properties: region_id (string), region_description (string)

// Node: territories
// Key: territory_id
// Properties: territory_id (string), territory_description (string)

// Relationship: SUPPLIES (suppliers -> products)
// Per supplier: 0..n products; Per product: 1..1 supplier (NOT NULL FK in PG)
// Cardinality: 0..n
// Source-Cardinality: 1..1

// Relationship: PURCHASED (customers -> orders)
// Per customer: 0..n orders; Per order: 1..1 customer (NOT NULL FK in PG)
// Cardinality: 0..n
// Source-Cardinality: 1..1

// Relationship: SOLD (employees -> orders)
// Per employee: 0..n orders; Per order: 1..1 employee (NOT NULL FK in PG)
// Cardinality: 0..n
// Source-Cardinality: 1..1

// Relationship: SHIPPED_VIA (orders -> shippers)
// Per order: 1..1 shipper (NOT NULL FK in PG); Per shipper: 0..n orders
// Cardinality: 1..1
// Source-Cardinality: 0..n

// Relationship: REPORTS_TO (employees -> employees)
// Per employee: 0..1 manager (self-ref, nullable FK); per manager: 0..n direct reports
// Cardinality: 0..1
// Source-Cardinality: 0..n

// Relationship: CONTAINS (orders -> products)
// Properties: unit_price (double), quantity (integer), discount (double)
// Per order: 0..n products; Per product: 0..n orders (M:N junction)
// Cardinality: 0..n
// Source-Cardinality: 0..n

// Relationship: HAS_CONTACT (customers -> contact)
// Per customer: 0..n contacts; Per contact: 1..1 customer (NOT NULL FK)
// Cardinality: 0..n
// Source-Cardinality: 1..1

// Relationship: BELONGS_TO (territories -> sales_region)
// Per territory: 1..1 sales_region (NOT NULL FK); Per sales_region: 0..n territories
// Cardinality: 1..1
// Source-Cardinality: 0..n

// Relationship: ASSIGNED_TO (employees -> territories)
// Per employee: 0..n territories; Per territory: 0..n employees (M:N via employee_territories)
// Cardinality: 0..n
// Source-Cardinality: 0..n
