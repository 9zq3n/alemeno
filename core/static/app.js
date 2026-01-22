// api base url - use relative path since we are serving from django now
const API_BASE = '';

const output = document.getElementById('output');

// tab switching
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));

        tab.classList.add('active');
        document.getElementById(tab.dataset.tab).classList.add('active');
    });
});

// api call wrapper
function showResponse(data, isError = false) {
    output.textContent = JSON.stringify(data, null, 2);
    output.className = isError ? 'error' : '';
}

// helper to get form data as object
function getFormData(form) {
    const formData = new FormData(form);
    const data = {};
    formData.forEach((val, key) => {
        // try to convert to number if possible
        const num = parseFloat(val);
        data[key] = isNaN(num) ? val : num;
    });
    return data;
}

// api call wrapper
async function apiCall(endpoint, method = 'GET', body = null) {
    try {
        const opts = {
            method,
            headers: { 'Content-Type': 'application/json' }
        };
        if (body) opts.body = JSON.stringify(body);

        const res = await fetch(API_BASE + endpoint, opts);

        // handle non-json responses (like 404 html pages) to avoid syntax errors
        const contentType = res.headers.get("content-type");
        if (!contentType || !contentType.includes("application/json")) {
            const text = await res.text();
            console.error("Non-JSON response:", text);
            throw new Error(`Server Error (${res.status}): ${res.statusText}`);
        }

        const data = await res.json();

        if (!res.ok) {
            showResponse(data, true);
            return null;
        }

        showResponse(data);
        return data;
    } catch (err) {
        showResponse({ error: 'Network/Server Error', details: err.message }, true);
        return null;
    }
}

// Register customer
document.getElementById('register-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = getFormData(e.target);
    await apiCall('/register', 'POST', data);
});

// Check eligibility
document.getElementById('eligibility-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = getFormData(e.target);
    await apiCall('/check-eligibility', 'POST', data);
});

// Create loan
document.getElementById('loan-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = getFormData(e.target);
    await apiCall('/create-loan', 'POST', data);
});

// View loans
document.getElementById('view-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const custId = e.target.customer_id.value;
    const loans = await apiCall(`/view-loans/${custId}`); // no trailing slash

    const listEl = document.getElementById('loans-list');
    listEl.innerHTML = '';

    if (loans && loans.length > 0) {
        loans.forEach(loan => {
            // simple text display
            listEl.innerHTML += `
                <div class="loan-item">
                    <div><b>Loan #${loan.loan_id}</b> <span style="margin: 0 5px">•</span> <span>₹${loan.loan_amount.toLocaleString()}</span></div>
                    <div><span>${loan.interest_rate}% Rate</span> <span style="margin: 0 5px">•</span> <span>₹${loan.monthly_installment.toLocaleString()}/mo</span></div>
                </div>
            `;
        });
    } else if (loans) {
        listEl.innerHTML = '<p style="color: #71717a; text-align: center;">No active loans found</p>';
    }
});

// View customer
document.getElementById('customer-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const custId = e.target.customer_id.value;
    await apiCall(`/view-customer/${custId}`);
});
