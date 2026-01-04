-- =============================================
-- Fix for orders table - Add missing columns
-- Run this in phpMyAdmin for book_ecommerce database
-- =============================================

-- Add the missing 'address' and 'name' columns to the orders table
-- These store delivery information for each order

ALTER TABLE `orders` 
ADD COLUMN `address` TEXT NULL AFTER `order_date`,
ADD COLUMN `name` VARCHAR(100) NULL AFTER `address`;

-- You can verify the change by running:
-- DESCRIBE orders;
