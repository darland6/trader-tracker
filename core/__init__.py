"""Core domain modules for the portfolio management system."""

from core.realities import (
    # From alt_history.py - Alternate History Management
    ensure_storage,
    load_index,
    save_index,
    list_histories,
    get_history,
    get_history_events,
    create_history,
    generate_modifications_from_description,
    apply_modifications,
    update_history,
    delete_history,
    compare_histories,
    find_divergence_points,
    create_seeded_reality,
    generate_algorithmic_trades,
    generate_llm_trading_history,
    build_historical_timeline,

    # From alternate_reality.py - Simple Reality Engine
    load_alternate_realities,
    save_alternate_realities,
    get_historical_prices,
    create_alternate_reality,
    generate_timeline_snapshots,
    get_alternate_reality,
    list_alternate_realities,
    delete_alternate_reality,
    refresh_alternate_reality,
    get_combined_timeline_data,

    # From reality_projections.py - Projections
    get_portfolio_context,
    build_projection_prompt,
    parse_llm_response,
    generate_fallback_projections,
    generate_projections,
    generate_projections_sync,

    # Storage paths
    DATA_DIR,
    ALT_HISTORIES_DIR,
    ALT_HISTORIES_INDEX,
    ALT_REALITIES_FILE,
)
