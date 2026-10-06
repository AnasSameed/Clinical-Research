-- ============================================
-- Daily SQL Practice: Window Functions
-- Topic: ROW_NUMBER, RANK, LAG/LEAD, running totals
-- ============================================

-- Sample data: sales reps and their monthly sales
CREATE TABLE sales (
    rep_id      INT,
    rep_name    VARCHAR(50),
    region      VARCHAR(20),
    sale_month  VARCHAR(10),
    amount      INT
);

INSERT INTO sales VALUES
(1, 'Asha',   'South', 'Jan', 5000),
(1, 'Asha',   'South', 'Feb', 7000),
(1, 'Asha',   'South', 'Mar', 4000),
(2, 'Ravi',   'South', 'Jan', 6000),
(2, 'Ravi',   'South', 'Feb', 6500),
(2, 'Ravi',   'South', 'Mar', 8000),
(3, 'Meera',  'North', 'Jan', 9000),
(3, 'Meera',  'North', 'Feb', 3000),
(3, 'Meera',  'North', 'Mar', 9500);


-- 1) ROW_NUMBER: give each row a unique sequence number per region,
--    ordered by amount descending (highest sale = row 1)
SELECT
    rep_name, region, sale_month, amount,
    ROW_NUMBER() OVER (PARTITION BY region ORDER BY amount DESC) AS rn
FROM sales;


-- 2) RANK vs DENSE_RANK: same idea, but ties share a rank.
--    RANK leaves a gap after a tie; DENSE_RANK doesn't.
SELECT
    rep_name, region, amount,
    RANK()       OVER (PARTITION BY region ORDER BY amount DESC) AS rnk,
    DENSE_RANK() OVER (PARTITION BY region ORDER BY amount DESC) AS dense_rnk
FROM sales;


-- 3) LAG: compare each month's sale to the PREVIOUS month for that rep
SELECT
    rep_name, sale_month, amount,
    LAG(amount, 1) OVER (PARTITION BY rep_id ORDER BY sale_month) AS prev_month_amount,
    amount - LAG(amount, 1) OVER (PARTITION BY rep_id ORDER BY sale_month) AS change
FROM sales;


-- 4) Running total: cumulative sales per rep, month over month
SELECT
    rep_name, sale_month, amount,
    SUM(amount) OVER (PARTITION BY rep_id ORDER BY sale_month
                       ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total
FROM sales;


-- ============================================
-- Notes (for quick interview recall):
-- - ROW_NUMBER   -> "top N per group" (e.g. top sale per region)
-- - RANK/DENSE_RANK -> leaderboards, ties matter
-- - LAG/LEAD     -> month-over-month / day-over-day comparisons
-- - SUM() OVER   -> running/cumulative totals (YTD style metrics)
-- ============================================
