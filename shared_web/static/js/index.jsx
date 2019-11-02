import Axios from "axios";
import React from "react";
import { render } from "react-dom";

class DeckTable extends React.Component {

  constructor() {
    super();
    this.state = {
      decks: [],
      page: 0,
      items: 50,
      sortBy: "date",
      sortOrder: "DESC"
    };
  }

  componentDidMount() {
    this.loadDecks();
  }

  componentDidUpdate(prevProps, prevState) {
    if (prevState.page !== this.state.page || prevState.sortBy !== this.state.sortBy || prevState.sortOrder !== this.state.sortOrder) {
      this.loadDecks();
    }
  }

  loadDecks() {
    const {page, items, sortBy, sortOrder} = this.state;
    Axios.get("/api/decks/", {"params": { "page": page, "items": items, "sortBy": sortBy, "sortOrder": sortOrder, "seasonId": this.props.seasonId }})
      .then(
        (response) => { this.setState({"decks": response.data.decks}) },
        (error) => console.log(error)
      );
  }

  render() {
    const className = "live with-marginalia" + (this.props.isVeryLarge ? "very-large" : "");
    const { decks, sortBy, sortOrder } = this.state;
    this.renderDeckRow = this.renderDeckRow.bind(this);
    const deckRows = decks.map(this.renderDeckRow);
    return (
      <div>
        <table className={className}>
          <thead>
              <tr>
                  <th data-breakpoints="xs" className="marginalia" onClick={this.sort.bind(this, "marginalia", "ASC")}>⇅</th>
                  <th data-breakpoints="xs sm">Colors</th>
                  <th onClick={this.sort.bind(this, "name", "ASC")}>Name</th>
                  { this.props.hidePerson
                    ? null
                    : <th data-breakpoints="xs" onClick={this.sort.bind(this, "person", "ASC")}>Person</th>
                  }
                  { this.props.showArchetype
                    ? <th data-breakpoints="xs sm md" onClick={this.sort.bind(this, "archetype", "ASC")}>Archetype</th>
                    : null
                  }
                  { this.props.hideSource
                    ? null
                    : <th data-breakpoints="xs sm md" onClick={this.sort.bind(this, "sourceName", "ASC")}>Source</th>
                  }
                  <th className="n" onClick={this.sort.bind(this, "record", "DESC")}>Record</th>
                  { this.props.showOmw
                    ? <th data-breakpoints="xs sm md" title="Opponent's Match Win" onClick={this.sort.bind(this, "omw", "DESC")}>OMW</th>
                    : null
                    }
                  { this.props.hideTop8
                    ? null
                    : <th className="c" data-breakpoints="xs sm" onClick={this.sort.bind(this, "top8", "ASC")}>Top 8</th>
                  }
                  <th data-breakpoints="xs" onClick={this.sort.bind(this, "date", "DESC")}>Date</th>
                  { this.props.showLegalSeasons
                    ? <th data-breakpoints="xs sm md" onClick={this.sort.bind(this, "season", "DESC")}>Season</th>
                    : null
                    }
                  {/* Empty column to hold the toggle when footable kicks in. */}
                  <td></td>
              </tr>
          </thead>
          <tbody>
            { this.props.activeRunsText
                ? <tr>
                      <td className="marginalia"><span className="active" title="Active in the current league">⊕</span></td>
                      <td></td>
                      <td>{this.props.activeRunsText}</td>
                  </tr>
                : null
            }
            {deckRows}
         </tbody>
        </table>
        <p><a onClick={this.movePage.bind(this, this.state.page - 1)}>Previous Page</a> | <a onClick={this.movePage.bind(this, this.state.page + 1)}>Next Page</a></p>
      </div>
    )
  }
  renderDeckRow(deck) {
    return (
      <tr key={deck.id}>
        <td className="marginalia" dangerouslySetInnerHTML={{__html: deck.starsSafe}}></td>
        <td dangerouslySetInnerHTML={{__html: deck.colorsSafe}} ></td>
        <td><a title={deck.decklist || null} href={deck.url}>{deck.name}</a></td>
        { this.props.hidePerson
          ? null
          : <td><a href={deck.personUrl} className="person">{deck.person}</a></td>
        }
        { this.props.showArchetype
          ? <td><a href={deck.archetypeUrl}>{deck.archetypeName}</a></td>
          : null
        }
        { this.props.hideSource
          ? null
          : (
              <td data-text={deck.sourceSort}>{/* are we displaying an empty data-text here now? */}
                { deck.competitionUrl
                  ? <a href={deck.competitionUrl}>{deck.sourceName}</a>
                  : <React.Fragment>{deck.sourceName}</React.Fragment>
                }
              </td>
            )
        }
        <td className="n">
            { deck.competitionUrl
              ? <a href={deck.competitionUrl}>{this.renderRecord(deck)}</a>
              : this.renderRecord(deck)
            }
        </td>
        { this.props.showOmw
          ? <td className="n">{deck.omw}</td>
          : null
        }
        { this.props.hideTop8
          ? null
          : <td className="c">
                { deck.competitionUrl
                  ? <a href={deck.competitionUrl} dangerouslySetInnerHTML={{__html: deck.top8Safe}}></a>
                  : <span dangerouslySetInnerHTML={{__html: deck.top8Safe}}></span>
                }
            </td>
        }
        <td data-text={deck.dateSort}>
            {deck.displayDate}
        </td>
        { this.props.showLegalSeasons
          ? <td dangerouslySetInnerHTML={{__html: deck.legalIcons}}></td>
          : null
        }
        {/* Empty column to hold the toggle when footable kicks in. */}
        <td></td>
      </tr>
    );
  }
  renderRecord(deck) {
    if (deck.showRecord && (deck.wins + deck.losses + deck.draws > 0)) {
        return deck.wins + "–" + deck.losses + (deck.draws ? "–" + deck.draws : "");
    }
    return "";
  }
  movePage(page) {
    this.setState({ "page": page })
  }
  sort(sortBy, sortOrder = "ASC") {
    if (this.state.sortBy === sortBy) {
      sortOrder = (this.state.sortOrder === "ASC" ? "DESC" : "ASC");
    }
    this.setState({ "sortBy": sortBy, "sortOrder": sortOrder, "page": 0 });
  }
}

const e = document.getElementById("decktable");
if (e !== null) {
  const table =
    <DeckTable
      activeRunsText={e.dataset.activeRunsText}
      hidePerson={e.dataset.hidePerson}
      hidePerson={e.dataset.hidePerson}
      hideSource={e.dataset.hideSource}
      hideTop8={e.dataset.hideTop8}
      isVeryLarge={e.dataset.isVeryLarge}
      seasonId={e.dataset.seasonId}
      showArchetype={e.dataset.showArchetype}
      showLegalSeasons={e.dataset.showLegalSeasons}
      showOmw={e.dataset.showOmw}
    />;
  render(table, e);
}
