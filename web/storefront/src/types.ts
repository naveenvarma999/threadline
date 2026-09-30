export interface Article {
  article_id: number;
  prod_name: string;
  product_type: string;
  product_group: string;
  colour: string;
  department: string;
  index_group: string;
  garment_group: string;
  description: string;
  price: string;
  image_url: string | null;
  score?: number;
  reason?: string;
  sources?: string[];
}

export interface FeedRow {
  key: string;
  title: string;
  items: Article[];
}

export interface Feed {
  model_version: string;
  fallback: boolean;
  rows: FeedRow[];
}

export interface Customer {
  customer_id: string;
  age: number | null;
  club_member_status: string;
  n_purchases: number;
}

export interface CustomerDetail extends Customer {
  recent_purchases: (Article & { purchased_at: string })[];
}

export interface Page<T> {
  count: number;
  next: string | null;
  results: T[];
}

export type EventType = "impression" | "click" | "add_to_cart" | "purchase";
