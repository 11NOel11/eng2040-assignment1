-- one row per order item with its product and seller attributes, for the feature step
select i.*,
       p.product_id is not null has_product, p.product_category_name, p.product_name_lenght, p.product_description_lenght,
       p.product_photos_qty, p.product_weight_g, p.product_length_cm, p.product_height_cm, p.product_width_cm,
       s.seller_id is not null has_seller, s.seller_zip_code_prefix, s.seller_city, s.seller_state
from order_items i
left join products p on p.product_id = i.product_id
left join sellers s on s.seller_id = i.seller_id
