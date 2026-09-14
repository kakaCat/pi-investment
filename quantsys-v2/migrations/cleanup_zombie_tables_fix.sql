-- Fix: Drop dependent views before dropping tables

-- Fix 1: public.strategy_performance
DROP VIEW IF EXISTS v_strategy_dashboard;
DROP TABLE IF EXISTS public.strategy_performance;

-- Fix 2: quant.daily_quotes  
DROP VIEW IF EXISTS quant_compat.daily_quotes;
DROP TABLE IF EXISTS quant.daily_quotes;
