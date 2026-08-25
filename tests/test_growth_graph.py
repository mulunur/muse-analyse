from app.agents.state import ContentIdea, GrowthState


def test_content_idea_and_growth_state_validate():
    idea = ContentIdea(
        id="idea-1",
        format="instagram_caption",
        hook="Тихое признание о новом треке.",
        rationale="Соответствует материалу артиста.",
        voice_alignment="Сдержанный тон",
    )
    state = GrowthState(artist_materials=["Короткое био"], content_ideas=[idea])
    assert state.content_ideas[0].id == "idea-1"
    assert state.retry_count == 0


def test_growth_graph_compiles():
    from app.agents.graph import build_growth_graph

    assert build_growth_graph() is not None