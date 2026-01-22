from django.shortcuts import render
from datetime import date
from dateutil.relativedelta import relativedelta
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import Customer, Loan
from .serializers import RegisterRequestSerializer, LoanRequestSerializer


@api_view(['GET'])
def api_info(request):
    return Response({
        'name': 'Credit Approval API',
        'endpoints': [
            'POST /register',
            'POST /check-eligibility', 
            'POST /create-loan',
            'GET /view-loan/<loan_id>',
            'GET /view-loans/<customer_id>',
            'GET /view-customer/<customer_id>'
        ]
    })


def home(request):
    return render(request, 'index.html')


# emi calculator - using standard reducing balance formula
def calc_emi(principal, rate, months):
    if rate == 0:
        return principal / months
    r = rate / 12 / 100
    emi = principal * r * ((1 + r) ** months) / (((1 + r) ** months) - 1)
    return round(emi, 2)


def get_credit_score(customer):
    """calculates score based on loan history, payment behavior etc
    returns 50 if no loan history exists"""
    customer_loans = Loan.objects.filter(customer=customer)
    
    if not customer_loans.exists():
        return 50
    
    loan_count = customer_loans.count()
    this_year = date.today().year
    loans_this_year = customer_loans.filter(start_date__year=this_year).count()
    
    total_tenure = sum(l.tenure for l in customer_loans)
    paid_on_time = sum(l.emis_paid_on_time for l in customer_loans)
    payment_ratio = paid_on_time / total_tenure if total_tenure > 0 else 0
    
    total_borrowed = float(sum(l.loan_amount for l in customer_loans))
    limit = float(customer.approved_limit)
    
    # if current debt > approved limit, reject outright
    active_loans = customer_loans.filter(end_date__gte=date.today())
    outstanding = float(sum(l.loan_amount for l in active_loans))
    
    if outstanding > limit:
        return 0
    
    score = 100
    # deduct for multiple loans
    score -= min(loan_count * 5, 20)
    score -= min(loans_this_year * 10, 20)
    score -= int((1 - payment_ratio) * 30)  # late payment penalty
    
    if limit > 0:
        utilization = total_borrowed / limit
        score -= min(int(utilization * 10), 20)
    
    return max(0, min(100, score))


def _get_min_rate(score, requested):
    """internal helper for interest rate correction"""
    if score > 50:
        return requested
    if score > 30:
        return max(requested, 12)
    if score > 10:
        return max(requested, 16)
    return requested


def _check_approval(customer, amt, rate, tenure):
    score = get_credit_score(customer)
    
    # calculate corrected rate and proposed emi
    corrected_rate = _get_min_rate(score, rate)
    proposed_emi = calc_emi(amt, corrected_rate, tenure)
    
    # emi should not exceed half of monthly income
    active = Loan.objects.filter(customer=customer, end_date__gte=date.today())
    current_total_emi = float(sum(l.monthly_repayment for l in active))
    
    if (current_total_emi + proposed_emi) > float(customer.monthly_salary) * 0.5:
        return (False, score)
    
    # score based approval
    if score > 50:
        return (True, score)
    elif score > 30:
        return (True, score) if rate >= 12 else (True, score)
    elif score > 10:
        return (True, score)
    
    return (False, score)


@api_view(['POST'])
def register(request):
    ser = RegisterRequestSerializer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
    
    data = ser.validated_data
    
    # round limit to nearest lakh (36x salary rule)
    limit = round(data['monthly_income'] * 36 / 100000) * 100000
    
    cust = Customer.objects.create(
        first_name=data['first_name'],
        last_name=data['last_name'],
        age=data['age'],
        phone_number=data['phone_number'],
        monthly_salary=data['monthly_income'],
        approved_limit=limit
    )
    
    return Response({
        'customer_id': cust.id,
        'name': f"{cust.first_name} {cust.last_name}",
        'age': cust.age,
        'monthly_income': int(cust.monthly_salary),
        'approved_limit': int(cust.approved_limit),
        'phone_number': cust.phone_number
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
def check_eligibility(request):
    ser = LoanRequestSerializer(data=request.data)
    if ser.is_valid() == False:
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
    
    data = ser.validated_data
    cust_id = data['customer_id']
    
    try:
        cust = Customer.objects.get(pk=cust_id)
    except Customer.DoesNotExist:
        return Response({'error': 'customer not found'}, status=404)
    
    approved, score = _check_approval(cust, data['loan_amount'], data['interest_rate'], data['tenure'])
    corrected_rate = _get_min_rate(score, data['interest_rate'])
    emi = calc_emi(data['loan_amount'], corrected_rate, data['tenure'])
    
    return Response({
        'customer_id': cust.id,
        'approval': approved,
        'interest_rate': data['interest_rate'],
        'corrected_interest_rate': corrected_rate,
        'tenure': data['tenure'],
        'monthly_installment': emi
    })


@api_view(['POST'])
def create_loan(request):
    ser = LoanRequestSerializer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
    
    data = ser.validated_data
    
    # fetch customer
    cust = Customer.objects.filter(id=data['customer_id']).first()
    if cust is None:
        return Response({'error': 'Customer does not exist'}, status=status.HTTP_404_NOT_FOUND)
    
    approved, score = _check_approval(cust, data['loan_amount'], data['interest_rate'], data['tenure'])
    corrected_rate = _get_min_rate(score, data['interest_rate'])
    emi = calc_emi(data['loan_amount'], corrected_rate, data['tenure'])
    
    if not approved:
        return Response({
            'loan_id': None,
            'customer_id': cust.id,
            'loan_approved': False,
            'message': 'Loan not approved based on credit score or EMI limit',
            'monthly_installment': emi
        })
    
    # create the loan
    today = date.today()
    end = today + relativedelta(months=data['tenure'])
    
    loan = Loan.objects.create(
        customer=cust,
        loan_amount=data['loan_amount'],
        tenure=data['tenure'],
        interest_rate=corrected_rate,
        monthly_repayment=emi,
        emis_paid_on_time=0,
        start_date=today,
        end_date=end
    )
    
    return Response({
        'loan_id': loan.id,
        'customer_id': cust.id,
        'loan_approved': True,
        'message': 'Loan approved',
        'monthly_installment': emi
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
def view_loan(request, loan_id):
    loan = Loan.objects.select_related('customer').filter(id=loan_id).first()
    if not loan:
        return Response({'error': 'Loan not found'}, status=status.HTTP_404_NOT_FOUND)
    
    c = loan.customer
    return Response({
        'loan_id': loan.id,
        'customer': {
            'id': c.id,
            'first_name': c.first_name,
            'last_name': c.last_name,
            'phone_number': c.phone_number,
            'age': c.age
        },
        'loan_amount': float(loan.loan_amount),
        'interest_rate': float(loan.interest_rate),
        'monthly_installment': float(loan.monthly_repayment),
        'tenure': loan.tenure
    })


@api_view(['GET'])
def view_loans(request, customer_id):
    # check if customer exists first
    if not Customer.objects.filter(id=customer_id).exists():
        return Response({'error': 'Customer not found'}, status=status.HTTP_404_NOT_FOUND)
    
    loans = Loan.objects.filter(customer_id=customer_id, end_date__gte=date.today())
    
    result = []
    for ln in loans:
        remaining = ln.tenure - ln.emis_paid_on_time
        if remaining < 0:
            remaining = 0  # shouldn't happen but just in case
        result.append({
            'loan_id': ln.id,
            'loan_amount': float(ln.loan_amount),
            'interest_rate': float(ln.interest_rate),
            'monthly_installment': float(ln.monthly_repayment),
            'repayments_left': remaining
        })
    
    return Response(result)


@api_view(['GET'])
def view_customer(request, customer_id):
    cust = Customer.objects.filter(id=customer_id).first()
    if not cust:
        return Response({'error': 'Customer not found'}, status=404)
    
    # get their loans too
    loans = Loan.objects.filter(customer=cust)
    active_count = loans.filter(end_date__gte=date.today()).count()
    
    return Response({
        'id': cust.id,
        'first_name': cust.first_name,
        'last_name': cust.last_name,
        'age': cust.age,
        'phone_number': cust.phone_number,
        'monthly_salary': float(cust.monthly_salary),
        'approved_limit': float(cust.approved_limit),
        'total_loans': loans.count(),
        'active_loans': active_count
    })
