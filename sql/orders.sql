-- one row per order. child tables are aggregated per order first, so joins cannot fan out.
-- left joins from orders, so no order is lost when a customer, item, payment or review is missing.
with it as (
  select order_id, count(*) n_items, count(distinct product_id) n_products, count(distinct seller_id) n_sellers,
         sum(price) price_sum, sum(freight_value) freight_sum,
         sum(case when price is null then 1 else 0 end) n_price_null,
         sum(case when freight_value is null then 1 else 0 end) n_freight_null
  from order_items group by order_id),
pay as (
  select order_id, count(*) n_payments, sum(payment_value) payment_sum_centavos,
         sum(case when payment_value is null then 1 else 0 end) n_payment_null
  from order_payments group by order_id),
rev as (
  select order_id, count(*) n_reviews from order_reviews group by order_id)
select o.*,
       c.customer_id is not null has_customer, c.customer_unique_id, c.customer_zip_code_prefix, c.customer_city, c.customer_state,
       coalesce(it.n_items, 0) n_items, it.n_products, it.n_sellers, it.price_sum, it.freight_sum, it.n_price_null, it.n_freight_null,
       coalesce(pay.n_payments, 0) n_payments, pay.payment_sum_centavos, pay.n_payment_null,
       coalesce(rev.n_reviews, 0) n_reviews
from orders o
left join customers c on c.customer_id = o.customer_id
left join it on it.order_id = o.order_id
left join pay on pay.order_id = o.order_id
left join rev on rev.order_id = o.order_id
