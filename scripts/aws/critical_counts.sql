SELECT table_name, row_count
FROM (
    SELECT 1 AS position, 'auth_user' AS table_name, COUNT(*)::bigint AS row_count
    FROM public.auth_user
    UNION ALL
    SELECT 2, 'core_userprofile', COUNT(*)::bigint
    FROM public.core_userprofile
    UNION ALL
    SELECT 3, 'core_company', COUNT(*)::bigint
    FROM public.core_company
    UNION ALL
    SELECT 4, 'core_product', COUNT(*)::bigint
    FROM public.core_product
    UNION ALL
    SELECT 5, 'core_inventory', COUNT(*)::bigint
    FROM public.core_inventory
    UNION ALL
    SELECT 6, 'core_order', COUNT(*)::bigint
    FROM public.core_order
    UNION ALL
    SELECT 7, 'core_orderitem', COUNT(*)::bigint
    FROM public.core_orderitem
    UNION ALL
    SELECT 8, 'core_payment', COUNT(*)::bigint
    FROM public.core_payment
    UNION ALL
    SELECT 9, 'core_shipment', COUNT(*)::bigint
    FROM public.core_shipment
    UNION ALL
    SELECT 10, 'core_logisticsevent', COUNT(*)::bigint
    FROM public.core_logisticsevent
    UNION ALL
    SELECT 11, 'core_companysubscription', COUNT(*)::bigint
    FROM public.core_companysubscription
    UNION ALL
    SELECT 12, 'core_adcampaign', COUNT(*)::bigint
    FROM public.core_adcampaign
    UNION ALL
    SELECT 13, 'django_migrations', COUNT(*)::bigint
    FROM public.django_migrations
    UNION ALL
    SELECT 14, 'django_session', COUNT(*)::bigint
    FROM public.django_session
    UNION ALL
    SELECT 15, 'axes_accesslog', COUNT(*)::bigint
    FROM public.axes_accesslog
) AS counts
ORDER BY position;
