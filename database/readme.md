# Database Documentation (DynamoDB)

This application uses Amazon DynamoDB as its serverless, NoSQL database layer. All tables are configured using **On-Demand** capacity mode.

---

## Table Schemas

### 1. `leave_balances`
Tracks the remaining leave quotas for each employee by year.
* **Partition Key (PK):** `employee_id` (String - `S`)
* **Sort Key (SK):** `leave_type_year` (String - `S`)
* **Secondary Indexes:** None

### 2. `leave_config`
Stores global application settings for different leave types (e.g., maximum allowed days per year).
* **Partition Key (PK):** `leave_type` (String - `S`)
* **Sort Key (SK):** None
* **Secondary Indexes:** None

### 3. `leave_requests`
Stores history and details of all leave requests submitted by employees.
* **Partition Key (PK):** `employee_id` (String - `S`)
* **Sort Key (SK):** `request_id` (String - `S`)
* **Secondary Indexes:** 1 Global Secondary Index (GSI):
  * **Index Name:** `manager_id-index`
  * **Partition Key (PK):** `manager_id` (String)
  * **Sort Key (SK):** `status` (String)
  * **Purpose:** Allows system to query and filter leave requests assigned to a specific manager by their current approval status.

---

## Database Architecture Visual
![DynamoDB Tables Setup](../screenshots/Dynamo_db_tables.jpg)
